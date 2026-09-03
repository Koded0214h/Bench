from __future__ import annotations

from datetime import datetime, timezone

from bench.audit.events import GENESIS_HASH, AuditEvent, EventKind


def make(seq: int, prev_hash: str, **kw) -> AuditEvent:
    return AuditEvent.create(seq=seq, kind=EventKind.NOTE, prev_hash=prev_hash, payload={"i": seq}, **kw)


def test_hash_is_deterministic_for_same_content():
    ts = datetime(2026, 9, 3, tzinfo=timezone.utc)
    a = AuditEvent.create(seq=0, kind="x", prev_hash=GENESIS_HASH, payload={"a": 1}, ts=ts, event_id="fixed")
    b = AuditEvent.create(seq=0, kind="x", prev_hash=GENESIS_HASH, payload={"a": 1}, ts=ts, event_id="fixed")
    assert a.hash == b.hash


def test_hash_changes_with_payload():
    ts = datetime(2026, 9, 3, tzinfo=timezone.utc)
    a = AuditEvent.create(seq=0, kind="x", prev_hash=GENESIS_HASH, payload={"a": 1}, ts=ts, event_id="fixed")
    b = AuditEvent.create(seq=0, kind="x", prev_hash=GENESIS_HASH, payload={"a": 2}, ts=ts, event_id="fixed")
    assert a.hash != b.hash


def test_recompute_matches_and_detects_tamper():
    ev = make(0, GENESIS_HASH)
    assert ev.hash_ok
    tampered = AuditEvent(
        seq=ev.seq, id=ev.id, ts=ev.ts, kind=ev.kind, prev_hash=ev.prev_hash,
        hash=ev.hash, payload={"i": 999},
    )
    assert not tampered.hash_ok


def test_round_trip_json():
    ev = make(3, "abc", actor="ceo", task_id="t1", worker_id="w1")
    back = AuditEvent.from_dict(__import__("json").loads(ev.to_json()))
    assert back == ev
    assert back.hash_ok


def test_payload_coerces_objects():
    class D:
        def to_dict(self):
            return {"effect": "DENY", "n": 1}

    ev = AuditEvent.create(seq=0, kind="x", prev_hash=GENESIS_HASH, payload={"decision": D()})
    assert ev.payload["decision"] == {"effect": "DENY", "n": 1}
