"""State and result types for the orchestration graph."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, TypedDict

from bench.agents.models import Review, TaskSpec, WorkerResult


class TaskStatus:
    RUNNING = "running"
    DENIED = "denied"
    ESCALATED = "escalated"      # awaiting a human (policy) or retry budget spent
    NEEDS_RETRY = "needs_retry"
    DONE = "done"
    REJECTED = "rejected"
    FAILED = "failed"

    TERMINAL = {DENIED, ESCALATED, DONE, REJECTED, FAILED}


class TaskState(TypedDict, total=False):
    spec: TaskSpec
    attempts: int
    max_attempts: int
    budget_estimate_usd: float
    skip_policy: bool
    status: str
    # step outputs
    decision: Any                # bench.policy.PolicyDecision
    worker_result: WorkerResult | None
    quarantine_result: Any       # bench.quarantine.QuarantineResult
    review: Review | None
    # carried between retries / to the caller
    failure: str | None
    escalation_reason: str | None
    machine_ids: list[str]


@dataclass
class TaskOutcome:
    task: TaskSpec
    status: str
    attempts: int
    worker_result: WorkerResult | None = None
    quarantine_result: Any = None
    review: Review | None = None
    decision: Any = None
    failure: str | None = None
    escalation_reason: str | None = None
    machine_ids: list[str] = field(default_factory=list)

    @property
    def accepted(self) -> bool:
        return self.status == TaskStatus.DONE

    @property
    def blocked(self) -> bool:
        return self.status in (TaskStatus.ESCALATED, TaskStatus.DENIED)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task.id, "title": self.task.title, "status": self.status,
            "attempts": self.attempts, "failure": self.failure,
            "escalation_reason": self.escalation_reason,
            "worker_result": self.worker_result.to_dict() if self.worker_result else None,
            "quarantine": self.quarantine_result.to_dict() if self.quarantine_result else None,
            "review": self.review.to_dict() if self.review else None,
            "machine_ids": list(self.machine_ids),
        }


@dataclass
class GoalRun:
    goal: str
    plan_notes: str
    outcomes: list[TaskOutcome] = field(default_factory=list)
    status: str = "done"          # done | blocked | failed

    @property
    def done(self) -> bool:
        return self.status == "done"

    def outcome_for(self, task_id: str) -> TaskOutcome | None:
        return next((o for o in self.outcomes if o.task.id == task_id), None)

    def to_dict(self) -> dict[str, Any]:
        return {
            "goal": self.goal, "status": self.status, "plan_notes": self.plan_notes,
            "outcomes": [o.to_dict() for o in self.outcomes],
        }


__all__ = ["TaskState", "TaskStatus", "TaskOutcome", "GoalRun"]
