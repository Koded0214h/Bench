"""``Orchestrator`` — decompose a goal, then drive each task through the graph."""

from __future__ import annotations

import concurrent.futures
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
            quarantine=quarantine, sink=self.sink,
            worker_max_steps=self.config.worker_max_steps, max_tokens=self.config.max_tokens,
        )
        self.audit = audit
        self.llm = llm
        self.company_context = company_context
        self._graph = build_task_graph(self._deps)

    # -- decomposition ---------------------------------------------------

    def decompose(self, goal: str) -> Plan:
        ceo = CEO(
            self.llm, company_context=self.company_context,
            max_tokens=self.config.max_tokens,
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
        run.outcomes = self._run_tasks(plan)

        if any(o.status in (TaskStatus.ESCALATED, TaskStatus.DENIED) for o in run.outcomes):
            run.status = "blocked"
        elif run.outcomes and all(o.status == TaskStatus.DONE for o in run.outcomes):
            run.status = "done"
        else:
            run.status = "failed"
        self.audit.task_state_changed(task_id=goal_id, to_state=run.status,
                                      reason=f"{len(run.outcomes)} task(s)")
        return run

    def _run_tasks(self, plan: Plan) -> list[TaskOutcome]:
        """Run every task in the plan, fanning independent ones out in
        parallel — a task starts the moment everything in its own
        ``depends_on`` has finished (successfully or not; a failed
        dependency still unblocks it, same as the old sequential walk over
        ``plan.ordered()`` did). Real concurrency is still capped by the
        meter's worker-pool slots (and, underneath that, by whatever your
        Solari account can actually run at once)."""

        outcomes: dict[str, TaskOutcome] = {}
        pending: dict[str, TaskSpec] = {t.id: t for t in plan.tasks}

        def satisfied(t: TaskSpec) -> bool:
            return all(dep in outcomes or plan.by_id(dep) is None for dep in t.depends_on)

        with concurrent.futures.ThreadPoolExecutor(thread_name_prefix="bench-task") as pool:
            futures: dict[concurrent.futures.Future, TaskSpec] = {}

            def schedule_ready() -> None:
                ready = [t for t in pending.values() if satisfied(t)]
                if not ready and pending and not futures:
                    # every remaining task is blocked on something that will
                    # never finish (a dependency cycle, or a bad reference) —
                    # run what's left rather than dropping it silently, the
                    # same escape hatch Plan.ordered() uses on a cycle.
                    ready = list(pending.values())
                for t in ready:
                    futures[pool.submit(self.run_task, t)] = t
                    del pending[t.id]

            schedule_ready()
            while futures:
                done, _ = concurrent.futures.wait(futures, return_when=concurrent.futures.FIRST_COMPLETED)
                for fut in done:
                    spec = futures.pop(fut)
                    outcomes[spec.id] = fut.result()
                schedule_ready()

        # a stable, dependency-respecting order for the caller — scheduling
        # order can otherwise vary run to run once tasks race each other.
        return [outcomes[t.id] for t in plan.ordered() if t.id in outcomes]

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
