"""Persist orchestration steps into the control-plane tables."""

from __future__ import annotations

from typing import Any

from django.utils import timezone as djtz

from bench.orchestration.state import TaskStatus

from .api.models import Agent, Dispatch, Escalation, Goal, Machine, Task

_STATUS_MAP = {
    TaskStatus.RUNNING: Task.Status.RUNNING,
    TaskStatus.DENIED: Task.Status.DENIED,
    TaskStatus.ESCALATED: Task.Status.ESCALATED,
    TaskStatus.NEEDS_RETRY: Task.Status.RUNNING,
    TaskStatus.DONE: Task.Status.DONE,
    TaskStatus.REJECTED: Task.Status.REJECTED,
    TaskStatus.FAILED: Task.Status.FAILED,
}


class DjangoSink:
    def __init__(self, goal: Goal) -> None:
        self.goal = goal
        self._agents: dict[str, str] = {}   # spec.id -> current worker agent id

    # -- plan -------------------------------------------------------

    def on_plan(self, plan) -> None:
        title_to_id = {}
        for spec in plan.tasks:
            row, _ = Task.objects.update_or_create(
                id=spec.id,
                defaults=dict(
                    goal=self.goal, title=spec.title, capability=spec.capability.value,
                    instructions=spec.instructions, success_criteria=list(spec.success_criteria),
                    depends_on=[], tool=spec.tool or None,
                ),
            )
            title_to_id[spec.title] = spec.id
        for spec in plan.tasks:
            resolved = [title_to_id.get(d, d) for d in spec.depends_on]
            Task.objects.filter(pk=spec.id).update(depends_on=resolved)
            spec.depends_on = resolved

    # -- per task -------------------------------------------------

    def on_task_status(self, spec, status: str, *, detail: str = "") -> None:
        mapped = _STATUS_MAP.get(status, status)
        Task.objects.filter(pk=spec.id).update(status=mapped, updated_at=djtz.now())

    def on_dispatch(self, spec, decision) -> None:
        Dispatch.objects.create(
            task_id=spec.id, capability=spec.capability.value,
            payload={"purpose": spec.title}, effect=decision.effect.value,
            audit=decision.audit, reason=decision.reason or "",
            matched_rules=[m.name for m in decision.matched],
        )

    def on_worker_hired(self, spec, worker_id: str) -> None:
        agent = Agent.objects.create(id=worker_id[:40], kind=Agent.Kind.WORKER,
                                     role=spec.capability.value, capability=spec.capability.value,
                                     task_id=spec.id)
        self._agents[spec.id] = agent.id
        Task.objects.filter(pk=spec.id).update(attempts=Task.objects.get(pk=spec.id).attempts + 1)

    def on_machine(self, spec, worker_id: str, handle) -> None:
        Machine.objects.update_or_create(
            id=getattr(handle, "id", f"unknown-{spec.id}"),
            defaults=dict(
                kind=getattr(getattr(handle, "kind", None), "value", spec.capability.value),
                status=Machine.Status.READY, task_id=spec.id,
                agent_id=self._agents.get(spec.id),
                stream_url=getattr(handle, "stream_url", None) or None,
            ),
        )

    def on_worker_result(self, spec, worker_id: str, result) -> None:
        Task.objects.filter(pk=spec.id).update(result=result.to_dict())
        aid = self._agents.get(spec.id)
        if aid:
            Agent.objects.filter(pk=aid).update(status=Agent.Status.DISMISSED, dismissed_at=djtz.now())
        Machine.objects.filter(task_id=spec.id, status=Machine.Status.READY).update(
            status=Machine.Status.DESTROYED, destroyed_at=djtz.now())

    def on_quarantine(self, spec, result) -> None:
        Task.objects.filter(pk=spec.id).update(quarantine=result.to_dict())

    def on_review(self, spec, review) -> None:
        Task.objects.filter(pk=spec.id).update(review=review.to_dict())

    def on_escalation(self, spec, reason: str) -> None:
        Escalation.objects.get_or_create(
            task_id=spec.id, status=Escalation.Status.PENDING,
            defaults=dict(reason=reason),
        )


__all__ = ["DjangoSink"]
