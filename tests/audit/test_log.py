from __future__ import annotations

import dataclasses

from bench.audit import AuditLog, EventKind
from bench.audit.events import AuditEvent


def test_append_chains_and_numbers():
    log = AuditLog()
    a = log.note("a")
    b = log.note("b")
    assert (a.seq, b.seq) == (0, 1)
    assert b.prev_hash == a.hash
    assert log.verify().ok


def test_verify_detects_broken_link():
    log = AuditLog()
    log.note("a")
    log.note("b")
    log.note("c")
    # Corrupt the middle event in place.
    events = log.store._events  # type: ignore[attr-defined]
    events[1] = dataclasses.replace(events[1], payload={"text": "tampered"})
    result = log.verify()
    assert not result.ok
    assert result.broken_at == 1


def test_verify_detects_missing_event():
    log = AuditLog()
    for c in "abcd":
        log.note(c)
    del log.store._events[2]  # type: ignore[attr-defined]
    result = log.verify()
    assert not result.ok
    assert result.broken_at == 2  # seq gap surfaces here


def test_dispatch_evaluated_flattens_decision():
    log = AuditLog()

    class Decision:
        effect = type("E", (), {"value": "ESCALATE"})()
        audit = True

        def to_dict(self):
            return {"effect": "ESCALATE", "audit": True, "matched": [{"name": "crm"}]}

    ev = log.dispatch_evaluated(task_id="t1", dispatch={"capability": "browser"}, decision=Decision())
    assert ev.kind == EventKind.DISPATCH_EVALUATED
    assert ev.payload["effect"] == "ESCALATE"
    assert ev.payload["audit"] is True
    assert ev.payload["decision"]["matched"][0]["name"] == "crm"


def test_recorders_populate_index_fields():
    log = AuditLog()
    log.task_created(task_id="t1", goal="ship it", actor="ceo")
    log.worker_hired(worker_id="w1", task_id="t1", capability="sandbox")
    log.machine_launched(machine_id="m1", kind="sandbox", task_id="t1", worker_id="w1")
    log.machine_destroyed(machine_id="m1", task_id="t1", worker_id="w1", reason="dismissed")
    log.worker_dismissed(worker_id="w1", task_id="t1", outcome="ok")

    assert [e.kind for e in log.events(task_id="t1")] == [
        EventKind.TASK_CREATED, EventKind.WORKER_HIRED, EventKind.MACHINE_LAUNCHED,
        EventKind.MACHINE_DESTROYED, EventKind.WORKER_DISMISSED,
    ]
    assert len(log.events(machine_id="m1")) == 2
    assert len(log.events(worker_id="w1")) == 4


def test_events_filters():
    log = AuditLog()
    log.note("x", task_id="a", actor="ceo")
    log.note("y", task_id="b", actor="ops")
    log.note("z", task_id="a", actor="ops")

    assert len(log.events(task_id="a")) == 2
    assert len(log.events(actor="ops")) == 2
    assert len(log.events(kinds=[EventKind.NOTE])) == 3
    assert len(log.events(since_seq=0)) == 2
    assert len(log.events(limit=1)) == 1
