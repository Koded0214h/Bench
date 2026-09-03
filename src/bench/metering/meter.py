"""``Meter`` — spend attribution, per-task budget ceilings, and the worker cap.

Two gates for the orchestrator:

* **Budget.** ``check_budget(task_id, estimate)`` before committing to spend;
  ``charge_*`` records what actually happened (and flags an overage).
* **Concurrency.** ``acquire_worker()`` before hiring; blocks or fails when the
  pool is at ``BENCH_MAX_WORKERS``.
"""

from __future__ import annotations

import threading
import time
from contextlib import contextmanager
from typing import Any, Callable, Iterator

from .config import MeteringConfig
from .errors import BudgetExceeded, WorkerPoolFull
from .models import Category, Charge, TaskUsage, WorkerSlot
from .rates import RateCard, default_rate_card

OnCharge = Callable[[Charge], None]


class Meter:
    def __init__(
        self,
        *,
        rate_card: RateCard | None = None,
        task_budget_usd: float | None = None,
        max_workers: int = 10,
        on_charge: OnCharge | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.rate_card = rate_card or default_rate_card()
        self.default_task_budget_usd = task_budget_usd
        self.max_workers = max_workers
        self._on_charge = on_charge
        self._clock = clock

        self._lock = threading.RLock()
        self._charges: list[Charge] = []
        self._task_budgets: dict[str, float | None] = {}
        self._active_slots: list[WorkerSlot] = []
        self._slots = threading.BoundedSemaphore(max_workers)

    @classmethod
    def from_config(cls, config: MeteringConfig, *, on_charge: OnCharge | None = None) -> "Meter":
        rate_card = RateCard.from_file(config.rate_card_path) if config.rate_card_path else default_rate_card()
        return cls(
            rate_card=rate_card,
            task_budget_usd=config.task_budget_usd,
            max_workers=config.max_workers,
            on_charge=on_charge,
        )

    @classmethod
    def from_env(cls, *, on_charge: OnCharge | None = None, **overrides: object) -> "Meter":
        return cls.from_config(MeteringConfig.from_env(**overrides), on_charge=on_charge)

    # -- budget --------------------------------------------------------

    def set_task_budget(self, task_id: str, usd: float | None) -> None:
        with self._lock:
            self._task_budgets[task_id] = usd

    def budget_for(self, task_id: str) -> float | None:
        with self._lock:
            return self._task_budgets.get(task_id, self.default_task_budget_usd)

    def total(self, task_id: str | None = None) -> float:
        with self._lock:
            rows = self._charges if task_id is None else [c for c in self._charges if c.task_id == task_id]
            return round(sum(c.amount_usd for c in rows), 6)

    def remaining(self, task_id: str) -> float | None:
        budget = self.budget_for(task_id)
        if budget is None:
            return None
        return round(budget - self.total(task_id), 6)

    def would_exceed(self, task_id: str, amount_usd: float) -> bool:
        budget = self.budget_for(task_id)
        return budget is not None and (self.total(task_id) + amount_usd) > budget + 1e-9

    def check_budget(self, task_id: str, amount_usd: float) -> None:
        """Raise :class:`BudgetExceeded` if spending ``amount_usd`` now would
        cross the ceiling. Pure check — records nothing."""

        with self._lock:
            budget = self.budget_for(task_id)
            spent = self.total(task_id)
        if budget is not None and (spent + amount_usd) > budget + 1e-9:
            raise BudgetExceeded(task_id, attempted_usd=amount_usd, spent_usd=spent, budget_usd=budget)

    # -- charging -----------------------------------------------------

    def charge(
        self,
        *,
        task_id: str,
        amount_usd: float,
        category: str = Category.OTHER,
        worker_id: str | None = None,
        machine_id: str | None = None,
        unit: str | None = None,
        quantity: float | None = None,
        detail: dict[str, Any] | None = None,
        raise_over: bool = False,
    ) -> Charge:
        """Record a charge against a task. Always recorded (the money is spent);
        ``over_budget`` is set when it crosses the ceiling, and ``raise_over``
        additionally raises :class:`BudgetExceeded` after recording."""

        if amount_usd < 0:
            raise ValueError("amount_usd must be >= 0")
        with self._lock:
            budget = self.budget_for(task_id)
            spent = self.total(task_id)
            over = budget is not None and (spent + amount_usd) > budget + 1e-9
            charge = Charge.create(
                task_id=task_id, category=category, amount_usd=round(amount_usd, 8),
                worker_id=worker_id, machine_id=machine_id, unit=unit, quantity=quantity,
                over_budget=over, detail=detail or {},
            )
            self._charges.append(charge)
        if self._on_charge is not None:
            self._on_charge(charge)
        if over and raise_over:
            raise BudgetExceeded(task_id, attempted_usd=amount_usd, spent_usd=spent, budget_usd=budget)  # type: ignore[arg-type]
        return charge

    def charge_machine_time(
        self, *, task_id: str, machine_id: str, kind: str, seconds: float,
        worker_id: str | None = None, raise_over: bool = False,
    ) -> Charge:
        usd = self.rate_card.machine_time_cost(kind, seconds)
        return self.charge(
            task_id=task_id, amount_usd=usd, category=Category.MACHINE_TIME,
            worker_id=worker_id, machine_id=machine_id, unit="seconds", quantity=round(seconds, 3),
            detail={"kind": kind}, raise_over=raise_over,
        )

    def charge_launch(
        self, *, task_id: str, machine_id: str, kind: str, worker_id: str | None = None,
    ) -> Charge:
        return self.charge(
            task_id=task_id, amount_usd=self.rate_card.launch_cost(kind), category=Category.LAUNCH,
            worker_id=worker_id, machine_id=machine_id, quantity=1, detail={"kind": kind},
        )

    def charge_llm(
        self, *, task_id: str, model: str, input_tokens: int, output_tokens: int,
        worker_id: str | None = None, raise_over: bool = False,
    ) -> Charge:
        usd, matched = self.rate_card.llm_cost(model, input_tokens, output_tokens)
        return self.charge(
            task_id=task_id, amount_usd=usd, category=Category.LLM, worker_id=worker_id,
            unit="tokens", quantity=input_tokens + output_tokens,
            detail={
                "model": model, "rate_key": matched, "priced": matched is not None,
                "input_tokens": input_tokens, "output_tokens": output_tokens,
            },
            raise_over=raise_over,
        )

    @contextmanager
    def machine_session(
        self, *, task_id: str, machine_id: str, kind: str, worker_id: str | None = None,
        charge_launch: bool = True,
    ) -> Iterator[dict[str, Any]]:
        """Time a block of machine use and charge for it on exit.

            with meter.machine_session(task_id=t, machine_id=m, kind="sandbox"):
                ... run the worker ...
        """

        if charge_launch:
            self.charge_launch(task_id=task_id, machine_id=machine_id, kind=kind, worker_id=worker_id)
        started = self._clock()
        info: dict[str, Any] = {"machine_id": machine_id, "kind": kind}
        try:
            yield info
        finally:
            elapsed = max(0.0, self._clock() - started)
            info["seconds"] = elapsed
            info["charge"] = self.charge_machine_time(
                task_id=task_id, machine_id=machine_id, kind=kind, seconds=elapsed, worker_id=worker_id,
            )

    # -- concurrency ------------------------------------------------

    @property
    def active_workers(self) -> int:
        with self._lock:
            return len(self._active_slots)

    @property
    def available_slots(self) -> int:
        return max(0, self.max_workers - self.active_workers)

    def acquire_worker(
        self, *, task_id: str | None = None, worker_id: str | None = None,
        blocking: bool = True, timeout: float | None = None,
    ) -> WorkerSlot:
        """Take a slot in the worker pool. Blocks until one frees, or raises
        :class:`WorkerPoolFull` when ``blocking=False`` / the timeout elapses."""

        got = self._slots.acquire(blocking=blocking, timeout=timeout)
        if not got:
            raise WorkerPoolFull(active=self.active_workers, cap=self.max_workers)
        slot = WorkerSlot(task_id=task_id, worker_id=worker_id, release=self._release_slot)
        with self._lock:
            self._active_slots.append(slot)
        return slot

    def try_acquire_worker(self, **kw: Any) -> WorkerSlot | None:
        try:
            return self.acquire_worker(blocking=False, **kw)
        except WorkerPoolFull:
            return None

    def _release_slot(self, slot: WorkerSlot) -> None:
        with self._lock:
            try:
                self._active_slots.remove(slot)
            except ValueError:
                return
        self._slots.release()

    # -- reporting ------------------------------------------------

    def charges(self, task_id: str | None = None) -> list[Charge]:
        with self._lock:
            if task_id is None:
                return list(self._charges)
            return [c for c in self._charges if c.task_id == task_id]

    def report(self, task_id: str) -> TaskUsage:
        with self._lock:
            rows = [c for c in self._charges if c.task_id == task_id]
            budget = self.budget_for(task_id)
        total = round(sum(c.amount_usd for c in rows), 6)
        by_category: dict[str, float] = {}
        by_worker: dict[str, float] = {}
        for c in rows:
            by_category[c.category] = round(by_category.get(c.category, 0.0) + c.amount_usd, 8)
            key = c.worker_id or "—"
            by_worker[key] = round(by_worker.get(key, 0.0) + c.amount_usd, 8)
        return TaskUsage(
            task_id=task_id,
            total_usd=total,
            charge_count=len(rows),
            budget_usd=budget,
            remaining_usd=(None if budget is None else round(budget - total, 6)),
            over_budget=(budget is not None and total > budget + 1e-9),
            by_category=by_category,
            by_worker=by_worker,
        )

    def tasks(self) -> list[str]:
        with self._lock:
            seen: list[str] = []
            for c in self._charges:
                if c.task_id not in seen:
                    seen.append(c.task_id)
            return seen


__all__ = ["Meter", "OnCharge"]
