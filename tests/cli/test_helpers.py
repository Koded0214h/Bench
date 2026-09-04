from __future__ import annotations

from bench.cli import load_dotenv
from bench.cli.stream import StreamingSink


def test_load_dotenv_reads_and_does_not_override(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text('FOO=from_file\nBAR="quoted value"\n# comment\nBLANKLINE\n\nBAZ=already\n')
    monkeypatch.delenv("FOO", raising=False)
    monkeypatch.setenv("BAZ", "from_env")

    load_dotenv(env)

    import os
    assert os.environ["FOO"] == "from_file"
    assert os.environ["BAR"] == "quoted value"
    assert os.environ["BAZ"] == "from_env"      # existing env wins


def test_load_dotenv_missing_file_is_noop(tmp_path):
    load_dotenv(tmp_path / "nope.env")          # must not raise


class SpySink:
    def __init__(self):
        self.calls: list[str] = []

    def __getattr__(self, name):
        def _rec(*a, **k):
            self.calls.append(name)
        return _rec


def test_streaming_sink_forwards_all_hooks(capsys):
    spy = SpySink()
    s = StreamingSink(spy)

    from types import SimpleNamespace
    spec = SimpleNamespace(title="T", capability=SimpleNamespace(value="sandbox"), depends_on=[])
    decision = SimpleNamespace(effect=SimpleNamespace(value="ALLOW"), audit=True, reason="ok")
    result = SimpleNamespace(ok=True, status=SimpleNamespace(value="done"), steps=3,
                             usage_input_tokens=1, usage_output_tokens=2, summary="did it", artifacts=[])
    review = SimpleNamespace(verdict=SimpleNamespace(value="ACCEPT"), reason="good")
    qr = SimpleNamespace(skipped=False, passed=True, checks=[], failure=None)
    plan = SimpleNamespace(tasks=[spec], ordered=lambda: [spec])

    s.on_plan(plan)
    s.on_dispatch(spec, decision)
    s.on_worker_hired(spec, "w1")
    s.on_machine(spec, "w1", SimpleNamespace(id="m1"))
    s.on_worker_result(spec, "w1", result)
    s.on_quarantine(spec, qr)
    s.on_review(spec, review)
    s.on_escalation(spec, "needs sign-off")
    s.on_task_status(spec, "running", detail="retry 1")

    assert spy.calls == [
        "on_plan", "on_dispatch", "on_worker_hired", "on_machine", "on_worker_result",
        "on_quarantine", "on_review", "on_escalation", "on_task_status",
    ]
    out = capsys.readouterr().out
    assert "plan" in out and "ALLOW" in out and "PASS" in out and "ACCEPT" in out
