"""The per-task lifecycle as a LangGraph state machine.

    policy_check ──deny/escalate──▶ END
        │ allow
        ▼
      work ──worker failed──▶ retry_gate ──budget left──▶ work
        │ ok                       │ spent
        ▼                          ▼
   quarantine ──fail──▶ retry_gate   ESCALATED ▶ END
        │ pass
        ▼
      review ─────────────────────▶ END   (done | rejected | escalated)

Failure is a first-class path: a bounded retry budget, then the task escalates
rather than looping forever.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from langgraph.graph import END, START, StateGraph

from bench.agents import CEO, build_worker
from bench.agents.models import WorkerStatus
from bench.metering import BudgetExceeded, WorkerPoolFull
from bench.policy import Dispatch as PolicyDispatch
from bench.quarantine import infer_spec

from .sink import NullSink, OrchestrationSink
from .state import TaskState, TaskStatus


@dataclass
class Deps:
    llm: Any
    solari: Any
    policy: Any
    meter: Any
    audit: Any
    quarantine: Any
    sink: OrchestrationSink
    worker_max_steps: int = 16

    def usage_cb(self, task_id: str):
        return lambda model, u: self.meter.charge_llm(
            task_id=task_id, model=model, input_tokens=u.input_tokens, output_tokens=u.output_tokens)


def _dispatch_for(spec) -> PolicyDispatch:
    cap = spec.capability.value
    return PolicyDispatch(
        capability=cap, action="write" if cap != "sandbox" else None, tool=spec.tool,
        domain=f"{spec.tool}.com" if spec.tool else None,
        network="external" if cap == "sandbox" else None, task_id=spec.id, agent="ceo",
        purpose=spec.title,
    )


def build_task_graph(deps: Deps):
    # -- nodes --------------------------------------------------------

    def policy_check(state: TaskState) -> dict:
        spec = state["spec"]
        if state.get("skip_policy"):
            # Resuming a task whose escalation a human already approved.
            return {"status": TaskStatus.RUNNING}
        dispatch = _dispatch_for(spec)
        decision = deps.policy.evaluate(dispatch)
        deps.audit.dispatch_evaluated(task_id=spec.id, dispatch=dict(dispatch.__dict__), decision=decision)
        deps.sink.on_dispatch(spec, decision)

        if decision.blocked:
            deps.audit.task_state_changed(task_id=spec.id, to_state="denied", reason=decision.reason)
            deps.sink.on_task_status(spec, TaskStatus.DENIED, detail=decision.reason or "")
            return {"decision": decision, "status": TaskStatus.DENIED}
        if decision.requires_approval:
            reason = decision.reason or "human sign-off required"
            deps.audit.escalation_raised(task_id=spec.id, reason=reason, decision=decision)
            deps.sink.on_escalation(spec, reason)
            deps.sink.on_task_status(spec, TaskStatus.ESCALATED, detail=reason)
            return {"decision": decision, "status": TaskStatus.ESCALATED, "escalation_reason": reason}
        return {"decision": decision, "status": TaskStatus.RUNNING}

    def work(state: TaskState) -> dict:
        spec = state["spec"]
        attempts = state.get("attempts", 0) + 1
        estimate = state.get("budget_estimate_usd", 0.10)
        try:
            deps.meter.check_budget(spec.id, estimate)
        except BudgetExceeded as exc:
            deps.audit.task_state_changed(task_id=spec.id, to_state="failed", reason=str(exc))
            deps.sink.on_task_status(spec, TaskStatus.FAILED, detail=str(exc))
            return {"status": TaskStatus.FAILED, "failure": str(exc), "attempts": attempts}

        try:
            slot = deps.meter.acquire_worker(task_id=spec.id, blocking=False)
        except WorkerPoolFull as exc:
            deps.audit.task_state_changed(task_id=spec.id, to_state="failed", reason=str(exc))
            deps.sink.on_task_status(spec, TaskStatus.FAILED, detail=str(exc))
            return {"status": TaskStatus.FAILED, "failure": str(exc), "attempts": attempts}

        prior = state.get("failure")
        if prior:
            spec.context = {**spec.context, "previous_attempt_failed_with": prior}

        worker_id = f"w_{spec.id.split('_')[-1]}_{state.get('attempts', 0)}"
        machine_ids = list(state.get("machine_ids", []))

        def on_machine(handle):
            mid = getattr(handle, "id", None)
            if mid:
                machine_ids.append(mid)
                deps.audit.machine_launched(machine_id=mid, kind=spec.capability.value,
                                            task_id=spec.id, worker_id=worker_id)
                deps.sink.on_machine(spec, worker_id, handle)

        worker = build_worker(spec, deps.llm, deps.solari, on_usage=deps.usage_cb(spec.id),
                              on_machine=on_machine, max_steps=deps.worker_max_steps)
        deps.audit.worker_hired(worker_id=worker_id, task_id=spec.id, capability=spec.capability.value)
        deps.sink.on_worker_hired(spec, worker_id)
        deps.sink.on_task_status(spec, TaskStatus.RUNNING, detail=f"attempt {state.get('attempts', 0) + 1}")

        with slot:
            result = worker.run(spec)

        for mid in machine_ids:
            deps.audit.machine_destroyed(machine_id=mid, task_id=spec.id, worker_id=worker_id, reason="dismissed")
        deps.audit.worker_dismissed(worker_id=worker_id, task_id=spec.id,
                                    outcome=result.status.value, reason=result.error)
        deps.sink.on_worker_result(spec, worker_id, result)

        if result.status is WorkerStatus.FAILED:
            return {"worker_result": result, "status": TaskStatus.NEEDS_RETRY, "attempts": attempts,
                    "failure": result.error or "worker failed", "machine_ids": machine_ids}
        return {"worker_result": result, "status": TaskStatus.RUNNING, "attempts": attempts,
                "machine_ids": machine_ids}

    def quarantine_node(state: TaskState) -> dict:
        spec, result = state["spec"], state["worker_result"]
        qresult = deps.quarantine.run(infer_spec(result))
        deps.audit.quarantine_result(task_id=spec.id, passed=qresult.passed,
                                     checks=[c.to_dict() for c in qresult.checks], failure=qresult.failure)
        deps.sink.on_quarantine(spec, qresult)
        if qresult.merged:
            return {"quarantine_result": qresult, "status": TaskStatus.RUNNING}
        return {"quarantine_result": qresult, "status": TaskStatus.NEEDS_RETRY,
                "failure": f"quarantine failed: {qresult.failure}"}

    def retry_gate(state: TaskState) -> dict:
        spec = state["spec"]
        attempts = state.get("attempts", 0)
        if attempts < state.get("max_attempts", 3):
            deps.audit.task_state_changed(task_id=spec.id, to_state="running",
                                          reason=f"retry {attempts}: {state.get('failure')}")
            deps.sink.on_task_status(spec, TaskStatus.RUNNING, detail=f"retry {attempts}")
            return {"status": TaskStatus.RUNNING}
        reason = f"retry budget spent ({attempts} attempts); last failure: {state.get('failure')}"
        deps.audit.escalation_raised(task_id=spec.id, reason=reason)
        deps.sink.on_escalation(spec, reason)
        deps.sink.on_task_status(spec, TaskStatus.ESCALATED, detail=reason)
        return {"status": TaskStatus.ESCALATED, "escalation_reason": reason}

    def review_node(state: TaskState) -> dict:
        spec, result = state["spec"], state["worker_result"]
        review = CEO(deps.llm, on_usage=deps.usage_cb(spec.id)).review(spec, result)
        mapping = {"ACCEPT": TaskStatus.DONE, "REJECT": TaskStatus.REJECTED, "ESCALATE": TaskStatus.ESCALATED}
        status = mapping[review.verdict.value]
        deps.audit.task_state_changed(task_id=spec.id, to_state=status, reason=review.reason)
        deps.sink.on_review(spec, review)
        deps.sink.on_task_status(spec, status, detail=review.reason)
        out = {"review": review, "status": status}
        if status == TaskStatus.ESCALATED:
            out["escalation_reason"] = review.reason
        return out

    # -- edges --------------------------------------------------------

    def after_policy(state: TaskState) -> str:
        return "work" if state["status"] == TaskStatus.RUNNING else END

    def after_work(state: TaskState) -> str:
        s = state["status"]
        if s == TaskStatus.NEEDS_RETRY:
            return "retry_gate"
        if s == TaskStatus.RUNNING:
            return "quarantine"
        return END

    def after_quarantine(state: TaskState) -> str:
        return "review" if state["status"] == TaskStatus.RUNNING else "retry_gate"

    def after_retry(state: TaskState) -> str:
        return "work" if state["status"] == TaskStatus.RUNNING else END

    g = StateGraph(TaskState)
    g.add_node("policy_check", policy_check)
    g.add_node("work", work)
    g.add_node("quarantine", quarantine_node)
    g.add_node("retry_gate", retry_gate)
    g.add_node("review", review_node)

    g.add_edge(START, "policy_check")
    g.add_conditional_edges("policy_check", after_policy, {"work": "work", END: END})
    g.add_conditional_edges("work", after_work, {"retry_gate": "retry_gate", "quarantine": "quarantine", END: END})
    g.add_conditional_edges("quarantine", after_quarantine, {"review": "review", "retry_gate": "retry_gate"})
    g.add_conditional_edges("retry_gate", after_retry, {"work": "work", END: END})
    g.add_edge("review", END)

    return g.compile()


__all__ = ["Deps", "build_task_graph"]
