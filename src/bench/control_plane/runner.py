"""Goal runner for the control plane — module 7's Orchestrator, persisted.

``run_goal`` builds an :class:`~bench.orchestration.Orchestrator` wired to the
DB-backed audit store, the metering charge sink, and :class:`DjangoSink` (which
writes Task / Agent / Machine / Dispatch / Escalation rows), then runs the goal.
Runs in a background thread.
"""

from __future__ import annotations

import threading
import traceback

from django.conf import settings

from bench.agents import FakeLLM, llm_from_env
from bench.agents.llm import LLMResponse, ToolCall, Usage
from bench.agents.models import TaskSpec
from bench.audit import AuditLog
from bench.metering import Meter
from bench.orchestration import Orchestrator, OrchestrationConfig
from bench.orchestration.state import TaskStatus
from bench.policy import PolicyEngine, PolicySet
from bench.quarantine import Quarantine
from bench.solari import SolariClient

from .api.models import Escalation, Goal, PolicyRule, Task
from .api.stores import DjangoAuditStore, record_charge
from .sink import DjangoSink


# --------------------------------------------------------------------------
# canned agents for BENCH_FAKE_LLM=1
# --------------------------------------------------------------------------

def _fake_llm() -> FakeLLM:
    plan = {"tasks": [{
        "title": "Build and serve the landing page",
        "capability": "sandbox",
        "instructions": "Write a single-file index.html for the product in the goal, serve it on port 8000, return the URL.",
        "success_criteria": ["index.html exists", "server responds on :8000", "a live URL is returned"],
    }]}
    page = "<!doctype html><meta charset=utf-8><title>Kobo</title><h1>Kobo</h1><p>Invoicing for freelancers.</p>"

    def wc(name, args, i):
        return LLMResponse(tool_calls=(ToolCall(f"w{i}", name, args),), stop_reason="tool_use", usage=Usage(500, 80))

    return FakeLLM(model="claude-sonnet-5", script=[
        LLMResponse(tool_calls=(ToolCall("c1", "submit_plan", plan),), stop_reason="tool_use", usage=Usage(400, 120)),
        wc("write_file", {"path": "index.html", "content": page}, 1),
        wc("run_command", {"cmd": "sh", "args": ["-c", "cd / && nohup python3 -m http.server 8000 >/tmp/s.log 2>&1 & sleep 1; echo up"]}, 2),
        wc("preview_port", {"port": 8000}, 3),
        wc("finish", {"status": "done", "summary": "Wrote index.html and served it on :8000.",
                      "artifacts": [{"kind": "url", "value": "(from preview_port)", "label": "live site"}]}, 4),
        LLMResponse(tool_calls=(ToolCall("c2", "submit_review",
                                         {"verdict": "ACCEPT", "reason": "served on :8000, live URL returned"}),),
                    stop_reason="tool_use", usage=Usage(300, 40)),
    ])


def _llm():
    return _fake_llm() if bool(getattr(settings, "BENCH_FAKE_LLM", False)) else llm_from_env()


def build_policy_engine() -> PolicyEngine:
    rows = list(PolicyRule.objects.all())
    if rows:
        return PolicyEngine(PolicySet.from_dicts(r.as_rule_dict() for r in rows))
    return PolicyEngine.from_env()


def _spec_from_row(row: Task) -> TaskSpec:
    return TaskSpec(
        title=row.title, capability=row.capability, instructions=row.instructions,
        success_criteria=list(row.success_criteria or []), depends_on=list(row.depends_on or []),
        tool=row.tool or None, id=row.id,
    )


def _make_orchestrator(goal: Goal, solari, sink) -> Orchestrator:
    return Orchestrator(
        llm=_llm(), solari=solari,
        policy=build_policy_engine(),
        meter=Meter.from_env(on_charge=record_charge),
        audit=AuditLog(DjangoAuditStore()),
        quarantine=Quarantine.from_env(solari),
        sink=sink,
        config=OrchestrationConfig.from_env(),
    )


# --------------------------------------------------------------------------

def run_goal(goal_id: str, *, sink_factory=DjangoSink) -> None:
    goal = Goal.objects.get(pk=goal_id)
    goal.status = Goal.Status.RUNNING
    goal.save(update_fields=["status", "updated_at"])

    with SolariClient.from_env(launch_timeout_s=150) as solari:
        orch = _make_orchestrator(goal, solari, sink_factory(goal))
        run = orch.run(goal.text, goal_id=goal.id)

    goal.refresh_from_db()
    goal.status = {"done": Goal.Status.DONE, "blocked": Goal.Status.BLOCKED,
                   "failed": Goal.Status.FAILED}.get(run.status, Goal.Status.FAILED)
    goal.notes = run.plan_notes or ""
    goal.save(update_fields=["status", "notes", "updated_at"])


def resume_after_escalation(escalation_id: str) -> None:
    esc = Escalation.objects.select_related("task__goal").get(pk=escalation_id)
    if esc.status != Escalation.Status.APPROVED:
        return
    row = esc.task
    goal = row.goal
    spec = _spec_from_row(row)

    audit = AuditLog(DjangoAuditStore())
    audit.escalation_resolved(task_id=row.id, approved=True, by=esc.resolved_by or "human")

    with SolariClient.from_env(launch_timeout_s=150) as solari:
        orch = _make_orchestrator(goal, solari, DjangoSink(goal))
        # The human approved the escalation — skip the policy gate this time.
        outcome = orch.run_task(spec, skip_policy=True)

    Task.objects.filter(pk=row.id).update(
        status={"done": Task.Status.DONE, "rejected": Task.Status.REJECTED,
                "escalated": Task.Status.ESCALATED, "failed": Task.Status.FAILED}
        .get(outcome.status, Task.Status.FAILED))

    # roll the goal status up
    states = list(Task.objects.filter(goal=goal).values_list("status", flat=True))
    if all(s == Task.Status.DONE for s in states) and states:
        goal.status = Goal.Status.DONE
    elif any(s in (Task.Status.ESCALATED,) for s in states):
        goal.status = Goal.Status.BLOCKED
    else:
        goal.status = Goal.Status.FAILED
    goal.save(update_fields=["status", "updated_at"])


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
