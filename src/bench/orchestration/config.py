"""Orchestration configuration from ``BENCH_*`` environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw)
    except ValueError:
        return default


@dataclass(frozen=True)
class OrchestrationConfig:
    #: Attempts per task = retries + 1. After that the task escalates.
    retry_limit: int = 2
    #: Pre-flight budget check per attempt (USD).
    budget_estimate_usd: float = 0.10
    worker_max_steps: int = 16
    max_tasks: int = 8
    #: Output-token cap per LLM call. Small values keep free-tier TPM budgets happy.
    max_tokens: int = 2048

    @property
    def max_attempts(self) -> int:
        return self.retry_limit + 1

    @classmethod
    def from_env(cls, **overrides: object) -> "OrchestrationConfig":
        values: dict[str, object] = {
            "retry_limit": _env_int("BENCH_RETRY_LIMIT", 2),
            "budget_estimate_usd": _env_float("BENCH_TASK_BUDGET_ESTIMATE_USD", 0.10),
            "worker_max_steps": _env_int("BENCH_WORKER_MAX_STEPS", 16),
            "max_tokens": _env_int("BENCH_LLM_MAX_TOKENS", 2048),
        }
        values.update(overrides)
        return cls(**values)  # type: ignore[arg-type]
