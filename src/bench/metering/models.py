"""Value types: a single charge, a per-task rollup, and a worker-pool slot."""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable


class Category:
    MACHINE_TIME = "machine_time"
    LAUNCH = "launch"
    LLM = "llm"
    OTHER = "other"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class Charge:
    id: str
    ts: str
    task_id: str
    category: str
    amount_usd: float
    worker_id: str | None = None
    machine_id: str | None = None
    unit: str | None = None            # "seconds" | "tokens" | ...
    quantity: float | None = None
    over_budget: bool = False
    detail: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(cls, **kw: Any) -> "Charge":
        kw.setdefault("id", uuid.uuid4().hex)
        kw.setdefault("ts", _now_iso())
        return cls(**kw)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id, "ts": self.ts, "task_id": self.task_id, "category": self.category,
            "amount_usd": self.amount_usd, "worker_id": self.worker_id, "machine_id": self.machine_id,
            "unit": self.unit, "quantity": self.quantity, "over_budget": self.over_budget,
            "detail": dict(self.detail),
        }


@dataclass(frozen=True)
class TaskUsage:
    task_id: str
    total_usd: float
    charge_count: int
    budget_usd: float | None = None
    remaining_usd: float | None = None
    over_budget: bool = False
    by_category: dict[str, float] = field(default_factory=dict)
    by_worker: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id, "total_usd": self.total_usd, "charge_count": self.charge_count,
            "budget_usd": self.budget_usd, "remaining_usd": self.remaining_usd,
            "over_budget": self.over_budget, "by_category": dict(self.by_category),
            "by_worker": dict(self.by_worker),
        }


class WorkerSlot:
    """A held place in the concurrent-worker pool. Context manager; releases once."""

    def __init__(
        self,
        *,
        task_id: str | None,
        worker_id: str | None,
        release: Callable[["WorkerSlot"], None],
    ) -> None:
        self.task_id = task_id
        self.worker_id = worker_id
        self.acquired_at = _now_iso()
        self._release = release
        self._released = threading.Event()

    @property
    def released(self) -> bool:
        return self._released.is_set()

    def release(self) -> None:
        if not self._released.is_set():
            self._released.set()
            self._release(self)

    def __enter__(self) -> "WorkerSlot":
        return self

    def __exit__(self, *exc: object) -> None:
        self.release()


__all__ = ["Charge", "TaskUsage", "WorkerSlot", "Category"]
