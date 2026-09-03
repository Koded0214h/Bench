from __future__ import annotations

from bench.audit import AuditLog, EventKind


def build_run() -> AuditLog:
    log = AuditLog()
    log.task_created(task_id="t1", goal="Launch a landing page and log it in Salesforce")
    log.task_state_changed(task_id="t1", from_state="created", to_state="dispatching")
    log.dispatch_evaluated(
        task_id="t1", dispatch={"capability": "sandbox"},
        decision={"effect": "ALLOW", "audit": False},
    )
    log.worker_hired(worker_id="w1", task_id="t1", capability="sandbox")
    log.machine_launched(machine_id="m1", kind="sandbox", task_id="t1", worker_id="w1")
    log.recording_captured(
        task_id="t1", worker_id="w1", machine_id="m1", recording_id="rec_abc",
        machine_kind="sandbox", replay_url="https://replays.getsolari.com/rec_abc",
    )
    log.quarantine_result(task_id="t1", worker_id="w1", passed=True, checks=["serves on :8000"])
    log.machine_destroyed(machine_id="m1", task_id="t1", worker_id="w1", reason="dismissed")
    log.worker_dismissed(worker_id="w1", task_id="t1", outcome="accepted")
    log.task_state_changed(task_id="t1", from_state="review", to_state="done")
    log.note("unrelated", task_id="t2")
    return log


def test_trace_scopes_to_task():
    trace = build_run().trace("t1")
    assert len(trace) == 10
    assert all(e.task_id == "t1" for e in trace)
    assert trace.workers() == ["w1"]
    assert trace.machines() == ["m1"]


def test_trace_recordings():
    recs = build_run().trace("t1").recordings()
    assert len(recs) == 1
    assert recs[0]["recording_id"] == "rec_abc"
    assert recs[0]["replay_url"].endswith("rec_abc")
    assert recs[0]["machine_id"] == "m1"


def test_trace_outcome_from_final_state():
    assert build_run().trace("t1").outcome() == "done"


def test_trace_outcome_escalated():
    log = AuditLog()
    log.task_created(task_id="t1", goal="write to CRM")
    log.escalation_raised(task_id="t1", reason="CRM write needs sign-off")
    assert log.trace("t1").outcome() == "escalated"


def test_trace_outcome_quarantine_failed():
    log = AuditLog()
    log.task_created(task_id="t1", goal="x")
    log.quarantine_result(task_id="t1", passed=False, failure="page 500s on /")
    assert log.trace("t1").outcome() == "quarantine-failed"


def test_trace_render_is_readable():
    text = build_run().trace("t1").render()
    assert "trace t1" in text
    assert "outcome=done" in text
    assert "recordings:" in text
    assert "rec_abc" in text


def test_trace_duration_present_with_multiple_events():
    trace = build_run().trace("t1")
    assert trace.duration_s() is not None and trace.duration_s() >= 0
