"""Bench audit trail — module 3.

The immutable record of everything the company did: every dispatch, every
machine, every policy decision, every session recording. Writes are append-only
and hash-chained; :meth:`AuditLog.verify` proves the chain is intact. Reads are
filtered queries and per-task :class:`Trace` views.

    from bench.audit import AuditLog

    audit = AuditLog.from_env()
    audit.task_created(task_id="t_1", goal="Launch a landing page")
    audit.dispatch_evaluated(task_id="t_1", dispatch=dispatch, decision=decision)
    ...
    print(audit.trace("t_1").render())
    assert audit.verify()
"""

from __future__ import annotations

from .config import AuditConfig, AuditConfigError
from .events import AuditEvent, EventKind
from .log import AuditLog, VerifyResult
from .store import AuditStore, InMemoryAuditStore, JsonlAuditStore
from .trace import Trace

__all__ = [
    "AuditLog",
    "VerifyResult",
    "AuditEvent",
    "EventKind",
    "Trace",
    "AuditConfig",
    "AuditConfigError",
    "AuditStore",
    "InMemoryAuditStore",
    "JsonlAuditStore",
]
