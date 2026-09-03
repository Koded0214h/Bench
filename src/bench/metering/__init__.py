"""Bench metering — module 4.

Spend attribution, per-task budget ceilings, and the concurrent-worker cap.

    from bench.metering import Meter

    meter = Meter.from_env()                       # BENCH_TASK_BUDGET_USD, BENCH_MAX_WORKERS

    meter.check_budget("t_1", estimate_usd)        # gate before committing spend
    with meter.acquire_worker(task_id="t_1"):      # gate before hiring (blocks at the cap)
        with meter.machine_session(task_id="t_1", machine_id="sbx_1", kind="sandbox"):
            ...                                     # machine time charged on exit
    print(meter.report("t_1").to_dict())
"""

from __future__ import annotations

from .config import MeteringConfig
from .errors import BudgetExceeded, MeteringConfigError, MeteringError, WorkerPoolFull
from .meter import Meter
from .models import Category, Charge, TaskUsage, WorkerSlot
from .rates import ModelRate, RateCard, default_rate_card

__all__ = [
    "Meter",
    "MeteringConfig",
    "RateCard",
    "ModelRate",
    "default_rate_card",
    "Charge",
    "TaskUsage",
    "WorkerSlot",
    "Category",
    "MeteringError",
    "MeteringConfigError",
    "BudgetExceeded",
    "WorkerPoolFull",
]
