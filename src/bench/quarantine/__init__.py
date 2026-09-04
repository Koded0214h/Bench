"""Bench quarantine — module 6.

The gate between "the agent produced a file" and "the thing works". Worker output
is rebuilt from data in a fresh Solari sandbox, its setup run, and its checks
executed. Only output that passes is cleared to merge.

    from bench.quarantine import Quarantine, QuarantineSpec, HttpServesCheck
    from bench.solari import SolariClient

    with SolariClient.from_env() as solari:
        q = Quarantine.from_env(solari)
        result = q.run(QuarantineSpec(
            files={"index.html": html},
            checks=[HttpServesCheck("serves", ["python3", "-m", "http.server", "8000"], 8000,
                                    body_contains="Kobo")],
        ))
        if not result.merged:
            ...  # hand result.failure back to the worker
"""

from __future__ import annotations

from .checks import (
    Check,
    CheckResult,
    CommandCheck,
    FileCheck,
    HttpServesCheck,
    ParsesCheck,
    PythonCheck,
    check_from_dict,
)
from .config import QuarantineConfig
from .models import QuarantineResult
from .runner import Quarantine
from .spec import QuarantineSpec, infer_spec

__all__ = [
    "Quarantine",
    "QuarantineConfig",
    "QuarantineSpec",
    "QuarantineResult",
    "infer_spec",
    "Check",
    "CheckResult",
    "CommandCheck",
    "PythonCheck",
    "FileCheck",
    "ParsesCheck",
    "HttpServesCheck",
    "check_from_dict",
]
