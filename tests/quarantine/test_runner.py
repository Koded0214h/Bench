from __future__ import annotations

from bench.quarantine import (
    CommandCheck,
    FileCheck,
    HttpServesCheck,
    Quarantine,
    QuarantineConfig,
    QuarantineSpec,
)
from tests.quarantine.conftest import FakeQBox, FakeSolari


def test_disabled_quarantine_skips_and_clears():
    q = Quarantine(FakeSolari(), config=QuarantineConfig(enabled=False))
    r = q.run(QuarantineSpec(files={"a.txt": "x"}))
    assert r.skipped and r.merged and r.passed
    # nothing launched
    assert q.solari.launched == []


def test_launch_failure_is_a_fail_not_a_raise():
    q = Quarantine(FakeSolari(fail=True))
    r = q.run(QuarantineSpec(files={"a.txt": "x"}, checks=[FileCheck("a", "a.txt")]))
    assert not r.passed and not r.merged
    assert "could not launch quarantine sandbox" in r.failure


def test_materializes_files_then_passes_all_checks():
    box = FakeQBox(lambda c, a, j: (0, "ok", ""))
    q = Quarantine(FakeSolari(box))
    spec = QuarantineSpec(
        files={"index.html": "<h1>Kobo</h1>", "sub/data.txt": "1"},
        checks=[FileCheck("html", "index.html", contains="Kobo"),
                CommandCheck("noop", "true")],
    )
    r = q.run(spec)
    assert r.passed and r.merged
    assert box.files["/workspace/index.html"] == "<h1>Kobo</h1>"
    assert box.files["/workspace/sub/data.txt"] == "1"
    assert ("mkdir", ["-p", "/workspace/sub"]) in box.execs
    assert box.closed is True
    assert r.sandbox_id == "qsbx_fake" and r.recording_id == "rec_q_fake"


def test_one_failing_check_makes_the_run_fail_with_reason():
    box = FakeQBox(lambda c, a, j: (0, "", ""))
    box.files["/workspace/index.html"] = "<h1>Kobo</h1>"
    q = Quarantine(FakeSolari(box))
    spec = QuarantineSpec(
        files={},
        checks=[FileCheck("html ok", "index.html"),
                FileCheck("has footer", "index.html", contains="FOOTER")],
    )
    r = q.run(spec)
    assert not r.passed
    assert "has footer" in r.failure and len(r.checks) == 2


def test_setup_failure_short_circuits_before_checks():
    def on_exec(cmd, args, joined):
        if cmd == "pip":
            return (1, "", "ERROR: No matching distribution found for leftpad")
        return (0, "", "")
    box = FakeQBox(on_exec)
    q = Quarantine(FakeSolari(box))
    spec = QuarantineSpec(
        files={"requirements.txt": "leftpad\n"},
        setup=[["pip", "install", "-r", "requirements.txt"]],
        checks=[FileCheck("never", "requirements.txt")],
    )
    r = q.run(spec)
    assert not r.passed
    assert "setup failed" in r.failure and "leftpad" in r.failure
    assert r.checks == []                       # checks never ran
    assert len(r.setup_log) == 1 and r.setup_log[0]["exit_code"] == 1


def test_spec_with_no_checks_fails_closed():
    q = Quarantine(FakeSolari(FakeQBox()))
    r = q.run(QuarantineSpec(files={"a.txt": "x"}))
    assert not r.passed and "nothing to verify" in r.failure


def test_check_that_raises_is_recorded_not_propagated():
    class Boom:
        name = "explodes"

        def run(self, box, ctx):
            raise RuntimeError("kaboom")

    q = Quarantine(FakeSolari(FakeQBox()))
    r = q.run(QuarantineSpec(files={}, checks=[Boom()]))
    assert not r.passed
    assert r.checks[0].name == "explodes" and "kaboom" in r.checks[0].detail


def test_on_event_stream():
    events = []
    box = FakeQBox(lambda c, a, j: (0, "", ""))
    q = Quarantine(FakeSolari(box), on_event=lambda k, d: events.append(k))
    q.run(QuarantineSpec(files={"a.txt": "x"}, checks=[FileCheck("a", "a.txt")]))
    assert events[0] == "start" and "check" in events and events[-1] == "done"


def test_run_bundle_convenience():
    box = FakeQBox(lambda c, a, j: (0, "200\nKobo\n", "") if "_qpoll" in j else (0, "", ""))
    q = Quarantine(FakeSolari(box))
    r = q.run_bundle(
        {"index.html": "<h1>Kobo</h1>"},
        checks=[HttpServesCheck("serves", ["python3", "-m", "http.server", "8000"], 8000, body_contains="Kobo")],
    )
    assert r.passed


def test_materializes_binary_files_via_write_bytes():
    box = FakeQBox(lambda c, a, j: (0, "16", ""))  # `wc -c` style check reports 16 bytes
    q = Quarantine(FakeSolari(box))
    raw = b"\x89PNG-fake-bytes"
    spec = QuarantineSpec(
        binary_files={"assets/icon.png": raw},
        checks=[CommandCheck("icon present", "sh", args=["-c", "true"])],
    )
    r = q.run(spec)
    assert r.passed
    assert box.binary_files["/workspace/assets/icon.png"] == raw
    assert ("mkdir", ["-p", "/workspace/assets"]) in box.execs
