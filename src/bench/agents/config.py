"""Agent configuration from ``BENCH_*`` / ``*_API_KEY`` environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass


class AgentsConfigError(ValueError):
    pass


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise AgentsConfigError(f"{name} must be an integer, got {raw!r}") from exc


@dataclass(frozen=True)
class AgentsConfig:
    model: str = "claude-sonnet-5"
    ceo_max_steps: int = 4
    worker_max_steps: int = 16
    max_tokens: int = 4096
    temperature: float = 0.0

    @classmethod
    def from_env(cls, **overrides: object) -> "AgentsConfig":
        values: dict[str, object] = {
            "model": os.environ.get("BENCH_LLM_MODEL", "claude-sonnet-5") or "claude-sonnet-5",
            "ceo_max_steps": _env_int("BENCH_CEO_MAX_STEPS", 4),
            "worker_max_steps": _env_int("BENCH_WORKER_MAX_STEPS", 16),
            "max_tokens": _env_int("BENCH_LLM_MAX_TOKENS", 4096),
        }
        values.update(overrides)
        return cls(**values)  # type: ignore[arg-type]
