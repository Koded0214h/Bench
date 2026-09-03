"""Audit log configuration from ``BENCH_AUDIT_*`` environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass

_BACKENDS = {"jsonl", "memory"}

DEFAULT_PATH = ".bench/audit.jsonl"


class AuditConfigError(ValueError):
    pass


@dataclass(frozen=True)
class AuditConfig:
    backend: str = "jsonl"
    path: str = DEFAULT_PATH

    def __post_init__(self) -> None:
        if self.backend not in _BACKENDS:
            raise AuditConfigError(
                f"BENCH_AUDIT_BACKEND must be one of {sorted(_BACKENDS)}, got {self.backend!r}"
            )

    @classmethod
    def from_env(cls, **overrides: object) -> "AuditConfig":
        values: dict[str, object] = {
            "backend": (os.environ.get("BENCH_AUDIT_BACKEND", "jsonl") or "jsonl").strip().lower(),
            "path": os.environ.get("BENCH_AUDIT_PATH", DEFAULT_PATH) or DEFAULT_PATH,
        }
        values.update(overrides)
        return cls(**values)  # type: ignore[arg-type]
