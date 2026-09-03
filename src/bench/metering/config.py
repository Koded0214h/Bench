"""Metering configuration from ``BENCH_*`` environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass

from .errors import MeteringConfigError


def _env_float(name: str) -> float | None:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return None
    try:
        return float(raw)
    except ValueError as exc:
        raise MeteringConfigError(f"{name} must be a number, got {raw!r}") from exc


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise MeteringConfigError(f"{name} must be an integer, got {raw!r}") from exc


@dataclass(frozen=True)
class MeteringConfig:
    #: Hard per-task ceiling in USD. None means unlimited (not recommended).
    task_budget_usd: float | None = None
    #: Concurrent worker cap.
    max_workers: int = 10
    #: Optional path to a rate card (YAML or JSON); None uses the bundled defaults.
    rate_card_path: str | None = None

    def __post_init__(self) -> None:
        if self.max_workers < 1:
            raise MeteringConfigError(f"max_workers must be >= 1, got {self.max_workers}")
        if self.task_budget_usd is not None and self.task_budget_usd < 0:
            raise MeteringConfigError("task_budget_usd must be >= 0")

    @classmethod
    def from_env(cls, **overrides: object) -> "MeteringConfig":
        values: dict[str, object] = {
            "task_budget_usd": _env_float("BENCH_TASK_BUDGET_USD"),
            "max_workers": _env_int("BENCH_MAX_WORKERS", 10),
            "rate_card_path": (os.environ.get("BENCH_RATE_CARD_PATH") or None),
        }
        values.update(overrides)
        return cls(**values)  # type: ignore[arg-type]
