"""``Orchestrator`` — decompose a goal, then drive each task through the graph."""

from __future__ import annotations

from typing import Any

from bench.agents import CEO
from bench.agents.models import Plan, TaskSpec

from .config import OrchestrationConfig
from .graph import Deps, build_task_graph
from .sink import NullSink, OrchestrationSink
from .state import GoalRun, TaskOutcome, TaskState, TaskStatus


class Orchestrator:
    def __init__(
        self,
        *,
        llm: Any,
        solari: Any,
        policy: Any,
        meter: Any,
        audit: Any,
        quarantine: Any,
        sink: OrchestrationSink | None = None,
        config: OrchestrationConfig | None = None,
        company_context: str = "",
    ) -> None:
        self.config = config or OrchestrationConfig()
        self.sink = sink or NullSink()
        self._deps = Deps(
            llm=llm, solari=solari, policy=policy, meter=meter, audit=audit,
            quarantine=quarantine, sink=self.sink, worker_max_steps=self.config.worker_max_steps,
        )
        self.audit = audit
        self.llm = llm
        self.company_context = company_context
        self._graph = build_task_graph(self._deps)

    # -- decomposition ---------------------------------------------------

    def decompose(self, goal: str) -> Plan:
        ceo = CEO(
            self.llm, company_context=self.company_context,
            on_usage=self._deps.usage_cb("__plan__"),
        )
        return ceo.decompose(goal, max_tasks=self.config.max_tasks)

    # -- run ----------------------------------------------------------

    def run(self, goal: str, *, goal_id: str | None = None) -> GoalRun:
        goal_id = goal_id or "goal"
        self.audit.task_created(task_id=goal_id, goal=goal, actor="ceo")
        try:
            plan = self.decompose(goal)
        except Exception as exc:  # noqa: BLE001
            self.audit.task_state_changed(task_id=goal_id, to_state="failed", reason=f"decompose: {exc}")
            return GoalRun(goal=goal, plan_notes="", status="failed")

        self.sink.on_plan(plan)
        run = GoalRun(goal=goal, plan_notes=plan.notes)

        for spec in plan.ordered():
            outcome = self.run_task(spec)
            run.outcomes.append(outcome)

        if any(o.status in (TaskStatus.ESCALATED, TaskStatus.DENIED) for o in run.outcomes):
            run.status = "blocked"
        elif run.outcomes and all(o.status == TaskStatus.DONE for o in run.outcomes):
            run.status = "done"
        else:
            run.status = "failed"
        self.audit.task_state_changed(task_id=goal_id, to_state=run.status,
                                      reason=f"{len(run.outcomes)} task(s)")
        return run

    def run_task(self, spec: TaskSpec, *, skip_policy: bool = False) -> TaskOutcome:
        initial: TaskState = {
            "spec": spec,
            "attempts": 0,
            "max_attempts": self.config.max_attempts,
            "budget_estimate_usd": self.config.budget_estimate_usd,
            "skip_policy": skip_policy,
            "status": TaskStatus.RUNNING,
            "machine_ids": [],
        }
        # LangGraph caps steps with recursion_limit; a task with N retries needs
        # ~4 nodes per attempt.
        final: TaskState = self._graph.invoke(
            initial, config={"recursion_limit": 6 + 4 * self.config.max_attempts}
        )
        return TaskOutcome(
            task=spec,
            status=final.get("status", TaskStatus.FAILED),
            attempts=final.get("attempts", 0),
            worker_result=final.get("worker_result"),
            quarantine_result=final.get("quarantine_result"),
            review=final.get("review"),
            decision=final.get("decision"),
            failure=final.get("failure"),
            escalation_reason=final.get("escalation_reason"),
            machine_ids=final.get("machine_ids", []),
        )


__all__ = ["Orchestrator"]
