"""Hand-wired goal runner — modules 1-6 stitched together, persisting to the DB.

This is the placeholder for module 7 (LangGraph orchestration). Same task
lifecycle as the README and ``scripts/flow_test.py``, but every step lands in the
control-plane tables and the DB-backed audit log. Runs in a background thread.
"""

from __future__ import annotations

import threading
import traceback
from datetime import datetime, timezone

from django.conf import settings
from django.utils import timezone as djtz

from bench.agents import CEO, FakeLLM, build_worker, llm_from_env
from bench.agents.llm import LLMResponse, ToolCall, Usage
from bench.agents.models import Plan, TaskSpec
from bench.audit import AuditLog
from bench.metering import BudgetExceeded, Meter, WorkerPoolFull
from bench.policy import Dispatch as PolicyDispatch
from bench.policy import PolicyEngine, PolicySet
from bench.quarantine import Quarantine, infer_spec
from bench.solari import SolariClient

from .api.models import Agent, Dispatch, Escalation, Goal, Machine, PolicyRule, Task
from .api.stores import DjangoAuditStore, record_charge

_RETRY_LIMIT = 1


# --------------------------------------------------------------------------
# fake LLMs (BENCH_FAKE_LLM=1) — one canned plan, one canned build, canned review
# --------------------------------------------------------------------------

def _fake_ceo() -> FakeLLM:
    plan = {"tasks": [{
        "title": "Build and serve the landing page",
        "capability": "sandbox",
        "instructions": "Write a single-file index.html for the product in the goal, serve it on port 8000, return the URL.",
        "success_criteria": ["index.html exists", "server responds on :8000", "a live URL is returned"],
    }]}
    review = {"verdict": "ACCEPT", "reason": "index.html is served on :8000 and a live URL was returned"}
    return FakeLLM(model="claude-sonnet-5", script=[
        LLMResponse(tool_calls=(ToolCall("c1", "submit_plan", plan),), stop_reason="tool_use", usage=Usage(400, 120)),
        LLMResponse(tool_calls=(ToolCall("c2", "submit_review", review),), stop_reason="tool_use", usage=Usage(300, 40)),
    ])


def _fake_worker() -> FakeLLM:
    page = "<!doctype html><meta charset=utf-8><title>Kobo</title><h1>Kobo</h1><p>Invoicing for freelancers.</p>"

    def c(name, args, i):
        return LLMResponse(tool_calls=(ToolCall(f"w{i}", name, args),), stop_reason="tool_use", usage=Usage(600, 90))

    return FakeLLM(model="claude-sonnet-5", script=[
        c("write_file", {"path": "index.html", "content": page}, 1),
        c("run_command", {"cmd": "sh", "args": ["-c", "cd / && nohup python3 -m http.server 8000 >/tmp/s.log 2>&1 & sleep 1; echo up"]}, 2),
        c("preview_port", {"port": 8000}, 3),
        c("finish", {"status": "done", "summary": "Wrote index.html and served it on :8000.",
                     "artifacts": [{"kind": "url", "value": "(from preview_port)", "label": "live site"}]}, 4),
    ])


# --------------------------------------------------------------------------

def build_policy_engine() -> PolicyEngine:
    rows = list(PolicyRule.objects.all())
    if rows:
        rules = PolicySet.from_dicts(r.as_rule_dict() for r in rows)
        return PolicyEngine(rules)
    return PolicyEngine.from_env()


def _spec_from_row(row: Task) -> TaskSpec:
    return TaskSpec(
        title=row.title, capability=row.capability, instructions=row.instructions,
        success_criteria=list(row.success_criteria or []), depends_on=list(row.depends_on or []),
        tool=row.tool or None, id=row.id,
    )


def _dispatch_for(spec: TaskSpec) -> PolicyDispatch:
    cap = spec.capability.value
    return PolicyDispatch(
        capability=cap, action="write" if cap != "sandbox" else None, tool=spec.tool,
        domain=f"{spec.tool}.com" if spec.tool else None,
        network="external" if cap == "sandbox" else None, task_id=spec.id, agent="ceo",
        purpose=spec.title,
    )


def run_goal(goal_id: str) -> None:
    fake = bool(getattr(settings, "BENCH_FAKE_LLM", False))
    goal = Goal.objects.get(pk=goal_id)
    goal.status = Goal.Status.PLANNING
    goal.save(update_fields=["status", "updated_at"])

    audit = AuditLog(DjangoAuditStore())
    policy = build_policy_engine()
    meter = Meter.from_env(on_charge=record_charge)

    def usage_cb(tid):
        return lambda model, u: meter.charge_llm(task_id=tid, model=model,
                                                 input_tokens=u.input_tokens, output_tokens=u.output_tokens)

    ceo_llm = _fake_ceo() if fake else llm_from_env()
    ceo = CEO(ceo_llm, on_usage=usage_cb(goal_id))
    Agent.objects.get_or_create(id="ceo", defaults=dict(kind=Agent.Kind.MANAGEMENT, role="ceo"))
    audit.task_created(task_id=goal_id, goal=goal.text, actor="ceo")

    try:
        plan: Plan = ceo.decompose(goal.text)
    except Exception as exc:  # noqa: BLE001
        goal.status = Goal.Status.FAILED
        goal.error = f"decomposition failed: {exc}"
        goal.save(update_fields=["status", "error", "updated_at"])
        audit.task_state_changed(task_id=goal_id, to_state="failed", reason=goal.error)
        return

    title_to_id: dict[str, str] = {}
    for spec in plan.tasks:
        row = Task.objects.create(
            goal=goal, title=spec.title, capability=spec.capability.value,
            instructions=spec.instructions, success_criteria=spec.success_criteria,
            depends_on=[], tool=spec.tool,
        )
        title_to_id[spec.title] = row.id
        spec.id = row.id
    for spec in plan.tasks:
        resolved = [title_to_id.get(d, d) for d in spec.depends_on]
        Task.objects.filter(pk=spec.id).update(depends_on=resolved)
        spec.depends_on = resolved

    goal.status = Goal.Status.RUNNING
    goal.notes = plan.notes or ""
    goal.save(update_fields=["status", "notes", "updated_at"])

    blocked = False
    with SolariClient.from_env(launch_timeout_s=150) as solari:
        quarantine = Quarantine.from_env(solari)
        for spec in plan.ordered():
            row = Task.objects.get(pk=spec.id)
            outcome = _run_task(spec, row, solari, quarantine, policy, meter, audit, usage_cb, fake)
            if outcome in ("escalated", "blocked"):
                blocked = True

    goal.refresh_from_db()
    states = list(Task.objects.filter(goal=goal).values_list("status", flat=True))
    if blocked or any(s in ("escalated",) for s in states):
        goal.status = Goal.Status.BLOCKED
    elif all(s == Task.Status.DONE for s in states) and states:
        goal.status = Goal.Status.DONE
    else:
        goal.status = Goal.Status.FAILED
    goal.save(update_fields=["status", "updated_at"])
    audit.task_state_changed(task_id=goal_id, to_state=goal.status, reason=f"{len(states)} task(s)")


def _run_task(spec, row, solari, quarantine, policy, meter, audit, usage_cb, fake) -> str:
    row.status = Task.Status.DISPATCHING
    row.save(update_fields=["status", "updated_at"])

    dispatch = _dispatch_for(spec)
    decision = policy.evaluate(dispatch)
    Dispatch.objects.create(
        task=row, capability=dispatch.capability, payload=dict(dispatch.__dict__),
        effect=decision.effect.value, audit=decision.audit, reason=decision.reason or "",
        matched_rules=[m.name for m in decision.matched],
    )
    audit.dispatch_evaluated(task_id=row.id, dispatch=dict(dispatch.__dict__), decision=decision)

    if decision.blocked:
        row.status = Task.Status.DENIED
        row.save(update_fields=["status", "updated_at"])
        audit.task_state_changed(task_id=row.id, to_state="denied", reason=decision.reason)
        return "denied"

    if decision.requires_approval:
        esc, _ = Escalation.objects.get_or_create(
            task=row, status=Escalation.Status.PENDING,
            defaults=dict(reason=decision.reason or "human sign-off required"),
        )
        row.status = Task.Status.ESCALATED
        row.save(update_fields=["status", "updated_at"])
        audit.escalation_raised(task_id=row.id, reason=decision.reason, decision=decision)
        return "escalated"

    return _hire_and_run(spec, row, solari, quarantine, meter, audit, usage_cb, fake)


def _hire_and_run(spec, row, solari, quarantine, meter, audit, usage_cb, fake, *, from_escalation=False) -> str:
    try:
        meter.check_budget(row.id, 0.10)
    except BudgetExceeded as exc:
        row.status = Task.Status.FAILED
        row.save(update_fields=["status", "updated_at"])
        audit.task_state_changed(task_id=row.id, to_state="failed", reason=str(exc))
        return "blocked"

    try:
        slot = meter.acquire_worker(task_id=row.id, blocking=False)
    except WorkerPoolFull as exc:
        row.status = Task.Status.FAILED
        row.save(update_fields=["status", "updated_at"])
        audit.task_state_changed(task_id=row.id, to_state="failed", reason=str(exc))
        return "blocked"

    worker_llm = _fake_worker() if fake else llm_from_env()
    agent = Agent.objects.create(kind=Agent.Kind.WORKER, role=spec.capability.value,
                                 capability=spec.capability.value, task=row)

    def on_machine(handle):
        Machine.objects.update_or_create(
            id=getattr(handle, "id", f"unknown-{row.id}"),
            defaults=dict(kind=getattr(getattr(handle, "kind", None), "value", spec.capability.value),
                          status=Machine.Status.READY, task=row, agent=agent,
                          stream_url=getattr(handle, "stream_url", None) or None),
        )

    worker = build_worker(spec, worker_llm, solari, on_usage=usage_cb(row.id), on_machine=on_machine)
    audit.worker_hired(worker_id=agent.id, task_id=row.id, capability=spec.capability.value)
    row.status = Task.Status.RUNNING
    row.attempts += 1
    row.save(update_fields=["status", "attempts", "updated_at"])

    with slot:
        result = worker.run(spec)

    Machine.objects.filter(agent=agent).update(status=Machine.Status.DESTROYED, destroyed_at=djtz.now())
    Agent.objects.filter(pk=agent.id).update(status=Agent.Status.DISMISSED, dismissed_at=djtz.now())
    audit.worker_dismissed(worker_id=agent.id, task_id=row.id, outcome=result.status.value, reason=result.error)
    row.result = result.to_dict()
    row.save(update_fields=["result", "updated_at"])

    if not result.ok:
        row.status = Task.Status.FAILED
        row.save(update_fields=["status", "updated_at"])
        audit.task_state_changed(task_id=row.id, to_state="failed", reason=result.error or "worker failed")
        return "failed"

    # quarantine
    row.status = Task.Status.QUARANTINE
    row.save(update_fields=["status", "updated_at"])
    qresult = quarantine.run(infer_spec(result))
    row.quarantine = qresult.to_dict()
    row.save(update_fields=["quarantine", "updated_at"])
    audit.quarantine_result(task_id=row.id, worker_id=agent.id, passed=qresult.passed,
                            checks=[c.to_dict() for c in qresult.checks], failure=qresult.failure)
    if not qresult.merged:
        row.status = Task.Status.FAILED
        row.save(update_fields=["status", "updated_at"])
        audit.task_state_changed(task_id=row.id, to_state="failed",
                                 reason=f"quarantine: {qresult.failure}")
        return "failed"

    # review
    row.status = Task.Status.REVIEW
    row.save(update_fields=["status", "updated_at"])
    review_llm = _fake_ceo() if fake else llm_from_env()
    try:
        review = CEO(review_llm).review(spec, result)
        state = {"ACCEPT": Task.Status.DONE, "REJECT": Task.Status.REJECTED,
                 "ESCALATE": Task.Status.ESCALATED}[review.verdict.value]
        row.status = state
        row.review = review.to_dict()
        row.save(update_fields=["status", "review", "updated_at"])
        audit.task_state_changed(task_id=row.id, to_state=state, reason=review.reason)
        return "done" if state == Task.Status.DONE else "failed"
    except Exception as exc:  # noqa: BLE001
        row.status = Task.Status.DONE
        row.review = {"verdict": "ACCEPT", "reason": f"auto-accepted (review unavailable: {exc})"}
        row.save(update_fields=["status", "review", "updated_at"])
        audit.task_state_changed(task_id=row.id, to_state="done", reason="review unavailable")
        return "done"


def resume_after_escalation(escalation_id: str) -> None:
    """Called after an escalation is approved: run the one task it gates."""

    esc = Escalation.objects.select_related("task__goal").get(pk=escalation_id)
    if esc.status != Escalation.Status.APPROVED:
        return
    row = esc.task
    spec = _spec_from_row(row)
    audit = AuditLog(DjangoAuditStore())
    audit.escalation_resolved(task_id=row.id, approved=True, by=esc.resolved_by or "human")
    meter = Meter.from_env(on_charge=record_charge)

    def usage_cb(tid):
        return lambda model, u: meter.charge_llm(task_id=tid, model=model,
                                                 input_tokens=u.input_tokens, output_tokens=u.output_tokens)

    with SolariClient.from_env(launch_timeout_s=150) as solari:
        quarantine = Quarantine.from_env(solari)
        _hire_and_run(spec, row, solari, quarantine, meter, audit, usage_cb,
                      bool(getattr(settings, "BENCH_FAKE_LLM", False)), from_escalation=True)


# --------------------------------------------------------------------------

def run_goal_in_thread(goal_id: str) -> threading.Thread:
    def _target() -> None:
        try:
            run_goal(goal_id)
        except Exception:  # noqa: BLE001
            try:
                g = Goal.objects.get(pk=goal_id)
                g.status = Goal.Status.FAILED
                g.error = traceback.format_exc()[-4000:]
                g.save(update_fields=["status", "error", "updated_at"])
            except Exception:  # noqa: BLE001
                pass

    t = threading.Thread(target=_target, name=f"bench-goal-{goal_id}", daemon=True)
    t.start()
    return t


def resume_in_thread(escalation_id: str) -> threading.Thread:
    t = threading.Thread(target=lambda: resume_after_escalation(escalation_id),
                         name=f"bench-esc-{escalation_id}", daemon=True)
    t.start()
    return t
