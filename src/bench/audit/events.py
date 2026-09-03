"""The audit event record and its tamper-evident hashing.

Every event carries the hash of the one before it. Editing or dropping any event
breaks the chain from that point on, which :func:`bench.audit.log.AuditLog.verify`
detects.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping

GENESIS_HASH = "0" * 64


class EventKind:
    """Well-known event kinds. ``kind`` is a free string; these are the ones the
    convenience recorders on :class:`AuditLog` emit."""

    TASK_CREATED = "task.created"
    TASK_STATE_CHANGED = "task.state_changed"

    DISPATCH_EVALUATED = "dispatch.evaluated"

    WORKER_HIRED = "worker.hired"
    WORKER_DISMISSED = "worker.dismissed"

    MACHINE_LAUNCHED = "machine.launched"
    MACHINE_DESTROYED = "machine.destroyed"

    QUARANTINE_RESULT = "quarantine.result"

    RECORDING_CAPTURED = "recording.captured"

    ESCALATION_RAISED = "escalation.raised"
    ESCALATION_RESOLVED = "escalation.resolved"

    COST_CHARGED = "cost.charged"

    NOTE = "note"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _isoformat(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


# Fields that feed the hash, in a fixed order. ``hash`` itself is excluded.
_HASHED_FIELDS = (
    "seq",
    "id",
    "ts",
    "kind",
    "actor",
    "task_id",
    "dispatch_id",
    "worker_id",
    "machine_id",
    "payload",
    "prev_hash",
)


@dataclass(frozen=True)
class AuditEvent:
    seq: int
    id: str
    ts: str
    kind: str
    prev_hash: str
    hash: str
    actor: str | None = None
    task_id: str | None = None
    dispatch_id: str | None = None
    worker_id: str | None = None
    machine_id: str | None = None
    payload: Mapping[str, Any] = field(default_factory=dict)

    # -- construction --------------------------------------------------

    @classmethod
    def create(
        cls,
        *,
        seq: int,
        kind: str,
        prev_hash: str,
        actor: str | None = None,
        task_id: str | None = None,
        dispatch_id: str | None = None,
        worker_id: str | None = None,
        machine_id: str | None = None,
        payload: Mapping[str, Any] | None = None,
        ts: datetime | None = None,
        event_id: str | None = None,
    ) -> "AuditEvent":
        body: dict[str, Any] = {
            "seq": seq,
            "id": event_id or uuid.uuid4().hex,
            "ts": _isoformat(ts or utcnow()),
            "kind": kind,
            "actor": actor,
            "task_id": task_id,
            "dispatch_id": dispatch_id,
            "worker_id": worker_id,
            "machine_id": machine_id,
            "payload": _plain(payload or {}),
            "prev_hash": prev_hash,
        }
        body["hash"] = _hash_body(body)
        return cls(**body)

    # -- hashing -----------------------------------------------------

    def recompute_hash(self) -> str:
        return _hash_body({f: getattr(self, f) for f in _HASHED_FIELDS})

    @property
    def hash_ok(self) -> bool:
        return self.recompute_hash() == self.hash

    # -- (de)serialization -----------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "seq": self.seq,
            "id": self.id,
            "ts": self.ts,
            "kind": self.kind,
            "actor": self.actor,
            "task_id": self.task_id,
            "dispatch_id": self.dispatch_id,
            "worker_id": self.worker_id,
            "machine_id": self.machine_id,
            "payload": dict(self.payload),
            "prev_hash": self.prev_hash,
            "hash": self.hash,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, separators=(",", ":"))

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "AuditEvent":
        return cls(
            seq=int(data["seq"]),
            id=str(data["id"]),
            ts=str(data["ts"]),
            kind=str(data["kind"]),
            prev_hash=str(data["prev_hash"]),
            hash=str(data["hash"]),
            actor=data.get("actor"),
            task_id=data.get("task_id"),
            dispatch_id=data.get("dispatch_id"),
            worker_id=data.get("worker_id"),
            machine_id=data.get("machine_id"),
            payload=dict(data.get("payload") or {}),
        )


def _hash_body(body: Mapping[str, Any]) -> str:
    canonical = json.dumps(
        {k: body[k] for k in _HASHED_FIELDS},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _plain(value: Any) -> Any:
    """Best-effort conversion of arbitrary objects to JSON-friendly data.

    Accepts things with ``to_dict()`` (e.g. a ``PolicyDecision``), dataclasses,
    mappings, and iterables; falls back to ``str``.
    """

    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Mapping):
        return {str(k): _plain(v) for k, v in value.items()}
    if hasattr(value, "to_dict") and callable(value.to_dict):
        return _plain(value.to_dict())
    if _is_dataclass_instance(value):
        import dataclasses

        return _plain(dataclasses.asdict(value))
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_plain(v) for v in value]
    if isinstance(value, datetime):
        return _isoformat(value)
    if isinstance(value, uuid.UUID):
        return value.hex
    return str(value)


def _is_dataclass_instance(value: Any) -> bool:
    import dataclasses

    return dataclasses.is_dataclass(value) and not isinstance(value, type)


__all__ = ["AuditEvent", "EventKind", "GENESIS_HASH", "utcnow"]
