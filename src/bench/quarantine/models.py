"""The result of a quarantine run."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .checks import CheckResult


@dataclass
class QuarantineResult:
    passed: bool
    skipped: bool = False
    checks: list[CheckResult] = field(default_factory=list)
    #: Concatenated reason(s) to hand back to the worker on failure.
    failure: str | None = None
    setup_log: list[dict[str, Any]] = field(default_factory=list)
    #: Recording of the quarantine sandbox itself, for the audit trail.
    recording_id: str | None = None
    sandbox_id: str | None = None
    duration_s: float = 0.0

    @property
    def merged(self) -> bool:
        """True when the output is cleared to merge (passed, or quarantine off)."""

        return self.passed or self.skipped

    def summary(self) -> str:
        if self.skipped:
            return "quarantine skipped (BENCH_QUARANTINE=false)"
        n = len(self.checks)
        ok = sum(1 for c in self.checks if c.passed)
        head = "PASS" if self.passed else "FAIL"
        return f"{head} — {ok}/{n} checks" + (f"; {self.failure}" if self.failure else "")

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed, "skipped": self.skipped,
            "checks": [c.to_dict() for c in self.checks],
            "failure": self.failure, "setup_log": self.setup_log,
            "recording_id": self.recording_id, "sandbox_id": self.sandbox_id,
            "duration_s": round(self.duration_s, 3),
        }


__all__ = ["QuarantineResult"]
