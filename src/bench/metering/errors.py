"""Errors raised by the metering module."""

from __future__ import annotations


class MeteringError(Exception):
    """Base for metering problems."""


class MeteringConfigError(MeteringError, ValueError):
    """Invalid metering configuration or rate card."""


class BudgetExceeded(MeteringError):
    """A charge (or a pre-flight check) would push a task past its ceiling."""

    def __init__(self, task_id: str, *, attempted_usd: float, spent_usd: float, budget_usd: float) -> None:
        self.task_id = task_id
        self.attempted_usd = attempted_usd
        self.spent_usd = spent_usd
        self.budget_usd = budget_usd
        self.overage_usd = round(spent_usd + attempted_usd - budget_usd, 6)
        super().__init__(
            f"task {task_id}: ${attempted_usd:.4f} would bring spend to "
            f"${spent_usd + attempted_usd:.4f}, over the ${budget_usd:.2f} ceiling "
            f"(by ${self.overage_usd:.4f})"
        )


class WorkerPoolFull(MeteringError):
    """All concurrent worker slots are taken and a non-blocking acquire failed."""

    def __init__(self, *, active: int, cap: int) -> None:
        self.active = active
        self.cap = cap
        super().__init__(f"worker pool full: {active}/{cap} slots in use")


__all__ = ["MeteringError", "MeteringConfigError", "BudgetExceeded", "WorkerPoolFull"]
