"""``AuditLog`` — the append-only record of everything the company did.

Every dispatch, every machine, every policy decision, every session recording.
Writes are append-only and hash-chained; :meth:`AuditLog.verify` proves the
chain is intact. Reads are filtered queries and per-task traces.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable, Iterator

from .config import AuditConfig
from .events import GENESIS_HASH, AuditEvent, EventKind
from .store import AuditStore, InMemoryAuditStore, JsonlAuditStore
from .trace import Trace


@dataclass(frozen=True)
class VerifyResult:
    ok: bool
    checked: int
    broken_at: int | None = None
    reason: str | None = None

    def __bool__(self) -> bool:
        return self.ok


class AuditLog:
    def __init__(self, store: AuditStore | None = None) -> None:
        # `is None`, not truthiness: an empty store has len 0 and is falsy.
        self._store: AuditStore = InMemoryAuditStore() if store is None else store
        self._lock = threading.RLock()

    @classmethod
    def from_config(cls, config: AuditConfig) -> "AuditLog":
        if config.backend == "memory":
            return cls(InMemoryAuditStore())
        return cls(JsonlAuditStore(config.path))

    @classmethod
    def from_env(cls, **overrides: object) -> "AuditLog":
        return cls.from_config(AuditConfig.from_env(**overrides))

    @property
    def store(self) -> AuditStore:
        return self._store

    # -- append -------------------------------------------------------

    def append(
        self,
        kind: str,
        *,
        actor: str | None = None,
        task_id: str | None = None,
        dispatch_id: str | None = None,
        worker_id: str | None = None,
        machine_id: str | None = None,
        payload: dict[str, Any] | None = None,
        ts: datetime | None = None,
    ) -> AuditEvent:
        """Append one event. Serialized across threads/processes so the hash
        chain and the gapless ``seq`` hold."""

        with self._lock, self._store.exclusive():
            last = self._store.last()
            seq = 0 if last is None else last.seq + 1
            prev_hash = GENESIS_HASH if last is None else last.hash
            event = AuditEvent.create(
                seq=seq,
                kind=kind,
                prev_hash=prev_hash,
                actor=actor,
                task_id=task_id,
                dispatch_id=dispatch_id,
                worker_id=worker_id,
                machine_id=machine_id,
                payload=payload or {},
                ts=ts,
            )
            self._store.append(event)
            return event

    # -- convenience recorders ------------------------------------

    def task_created(
        self, *, task_id: str, goal: str, parent_id: str | None = None,
        success_criteria: Any = None, actor: str | None = None,
    ) -> AuditEvent:
        return self.append(
            EventKind.TASK_CREATED, task_id=task_id, actor=actor,
            payload={"goal": goal, "parent_id": parent_id, "success_criteria": success_criteria},
        )

    def task_state_changed(
        self, *, task_id: str, to_state: str, from_state: str | None = None,
        reason: str | None = None, actor: str | None = None,
    ) -> AuditEvent:
        return self.append(
            EventKind.TASK_STATE_CHANGED, task_id=task_id, actor=actor,
            payload={"from": from_state, "to": to_state, "reason": reason},
        )

    def dispatch_evaluated(
        self, *, dispatch: Any, decision: Any, task_id: str | None = None,
        dispatch_id: str | None = None, actor: str | None = None,
    ) -> AuditEvent:
        payload = {"dispatch": dispatch, "decision": decision}
        effect = _get(decision, "effect")
        if effect is not None:
            payload["effect"] = getattr(effect, "value", effect)
        payload["audit"] = bool(_get(decision, "audit", False))
        return self.append(
            EventKind.DISPATCH_EVALUATED, task_id=task_id, dispatch_id=dispatch_id,
            actor=actor, payload=payload,
        )

    def worker_hired(
        self, *, worker_id: str, task_id: str, capability: str,
        dispatch_id: str | None = None, actor: str | None = None,
    ) -> AuditEvent:
        return self.append(
            EventKind.WORKER_HIRED, worker_id=worker_id, task_id=task_id,
            dispatch_id=dispatch_id, actor=actor, payload={"capability": capability},
        )

    def worker_dismissed(
        self, *, worker_id: str, task_id: str, outcome: str,
        reason: str | None = None, actor: str | None = None,
    ) -> AuditEvent:
        return self.append(
            EventKind.WORKER_DISMISSED, worker_id=worker_id, task_id=task_id,
            actor=actor, payload={"outcome": outcome, "reason": reason},
        )

    def machine_launched(
        self, *, machine_id: str, kind: str, task_id: str | None = None,
        worker_id: str | None = None, limits: dict[str, Any] | None = None,
        actor: str | None = None,
    ) -> AuditEvent:
        return self.append(
            EventKind.MACHINE_LAUNCHED, machine_id=machine_id, task_id=task_id,
            worker_id=worker_id, actor=actor, payload={"kind": kind, "limits": limits or {}},
        )

    def machine_destroyed(
        self, *, machine_id: str, task_id: str | None = None, worker_id: str | None = None,
        reason: str | None = None,
    ) -> AuditEvent:
        return self.append(
            EventKind.MACHINE_DESTROYED, machine_id=machine_id, task_id=task_id,
            worker_id=worker_id, payload={"reason": reason},
        )

    def quarantine_result(
        self, *, task_id: str, passed: bool, worker_id: str | None = None,
        checks: Any = None, failure: str | None = None,
    ) -> AuditEvent:
        return self.append(
            EventKind.QUARANTINE_RESULT, task_id=task_id, worker_id=worker_id,
            payload={"passed": passed, "checks": checks, "failure": failure},
        )

    def recording_captured(
        self, *, recording_id: str, task_id: str | None = None, worker_id: str | None = None,
        machine_id: str | None = None, provider: str = "solari", machine_kind: str | None = None,
        replay_url: str | None = None, expires_at: str | None = None,
    ) -> AuditEvent:
        return self.append(
            EventKind.RECORDING_CAPTURED, task_id=task_id, worker_id=worker_id,
            machine_id=machine_id,
            payload={
                "provider": provider, "recording_id": recording_id,
                "machine_kind": machine_kind, "replay_url": replay_url, "expires_at": expires_at,
            },
        )

    def escalation_raised(
        self, *, task_id: str, reason: str | None = None, decision: Any = None,
        actor: str | None = None,
    ) -> AuditEvent:
        return self.append(
            EventKind.ESCALATION_RAISED, task_id=task_id, actor=actor,
            payload={"reason": reason, "decision": decision},
        )

    def escalation_resolved(
        self, *, task_id: str, approved: bool, by: str | None = None, note: str | None = None,
    ) -> AuditEvent:
        return self.append(
            EventKind.ESCALATION_RESOLVED, task_id=task_id, actor=by,
            payload={"approved": approved, "by": by, "note": note},
        )

    def cost_charged(
        self, *, task_id: str, amount_usd: float, worker_id: str | None = None,
        unit: str | None = None, detail: Any = None,
    ) -> AuditEvent:
        return self.append(
            EventKind.COST_CHARGED, task_id=task_id, worker_id=worker_id,
            payload={"amount_usd": amount_usd, "unit": unit, "detail": detail},
        )

    def note(self, text: str, *, task_id: str | None = None, actor: str | None = None, **fields: Any) -> AuditEvent:
        return self.append(EventKind.NOTE, task_id=task_id, actor=actor, payload={"text": text, **fields})

    # -- queries ---------------------------------------------------

    def all(self) -> list[AuditEvent]:
        return self._store.read_all()

    def events(
        self,
        *,
        kinds: Iterable[str] | None = None,
        task_id: str | None = None,
        dispatch_id: str | None = None,
        worker_id: str | None = None,
        machine_id: str | None = None,
        actor: str | None = None,
        since_seq: int | None = None,
        limit: int | None = None,
    ) -> list[AuditEvent]:
        kind_set = set(kinds) if kinds is not None else None
        out: list[AuditEvent] = []
        for ev in self._store.read_all():
            if kind_set is not None and ev.kind not in kind_set:
                continue
            if task_id is not None and ev.task_id != task_id:
                continue
            if dispatch_id is not None and ev.dispatch_id != dispatch_id:
                continue
            if worker_id is not None and ev.worker_id != worker_id:
                continue
            if machine_id is not None and ev.machine_id != machine_id:
                continue
            if actor is not None and ev.actor != actor:
                continue
            if since_seq is not None and ev.seq <= since_seq:
                continue
            out.append(ev)
            if limit is not None and len(out) >= limit:
                break
        return out

    def trace(self, task_id: str) -> Trace:
        return Trace(task_id, self.events(task_id=task_id))

    # -- integrity ----------------------------------------------

    def verify(self) -> VerifyResult:
        """Walk the chain: gapless ``seq``, correct ``prev_hash`` links, and each
        event's own ``hash`` recomputes."""

        prev_hash = GENESIS_HASH
        events = self._store.read_all()
        for i, ev in enumerate(events):
            if ev.seq != i:
                return VerifyResult(False, i, i, f"seq gap: expected {i}, got {ev.seq}")
            if ev.prev_hash != prev_hash:
                return VerifyResult(False, len(events), ev.seq, f"prev_hash mismatch at seq {ev.seq}")
            if not ev.hash_ok:
                return VerifyResult(False, len(events), ev.seq, f"hash mismatch at seq {ev.seq}")
            prev_hash = ev.hash
        return VerifyResult(True, len(events))

    # -- dunder --------------------------------------------------

    def __len__(self) -> int:
        return len(self._store)

    def __iter__(self) -> Iterator[AuditEvent]:
        return iter(self._store.read_all())


def _get(obj: Any, name: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


__all__ = ["AuditLog", "VerifyResult"]
