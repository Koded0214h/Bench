"""Quarantine configuration from ``BENCH_*`` environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


@dataclass(frozen=True)
class QuarantineConfig:
    #: BENCH_QUARANTINE=false merges output untested. Don't.
    enabled: bool = True
    #: Sandbox template for the clean rebuild environment.
    template: str | None = None
    #: Hard lifetime for the quarantine sandbox (ms).
    timeout_ms: int = 5 * 60_000
    #: Seconds allowed for each setup command.
    setup_timeout_s: int = 180
    #: Record the quarantine sandbox so failures can be watched.
    record: bool = True

    @classmethod
    def from_env(cls, **overrides: object) -> "QuarantineConfig":
        values: dict[str, object] = {
            "enabled": _env_bool("BENCH_QUARANTINE", True),
            "template": os.environ.get("BENCH_QUARANTINE_TEMPLATE") or None,
            "timeout_ms": _env_int("BENCH_QUARANTINE_TIMEOUT_MS", 5 * 60_000),
        }
        values.update(overrides)
        return cls(**values)  # type: ignore[arg-type]
