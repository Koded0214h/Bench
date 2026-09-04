"""The hand-wired runner, driven with fake LLMs and a fake Solari."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from django.test import override_settings

from bench.control_plane.api.models import Agent, Dispatch, Goal, Machine, Task

pytestmark = pytest.mark.django_db


class FakeSandboxHandle:
    def __init__(self):
        self.id = "sbx_runner_fake"
        self.kind = SimpleNamespace(value="sandbox")
        self.files: dict[str, str] = {}
        self.closed = False

    def __enter__(self): return self
    def __exit__(self, *e): self.closed = True

    def exec(self, cmd, *, args=None, cwd=None, env=None, timeout_ms=None, background=False):
        return SimpleNamespace(exitCode=0, stdout="ok", stderr="")

    def write_text(self, p, c): self.files[p] = c
    def read_text(self, p): return self.files.get(p, "")
    def preview_url(self, port): return f"https://sbx_runner_fake-{port}.preview.getsolari.com"


class FakeSolari:
    def __init__(self):
        self.sandboxes: list[FakeSandboxHandle] = []

    def launch_sandbox(self, **kw):
        h = FakeSandboxHandle()
        self.sandboxes.append(h)
        return h

    def __enter__(self): return self
    def __exit__(self, *e): pass


@pytest.fixture
def patched(monkeypatch):
    """Fake Solari + a quarantine that always passes, so the runner is offline."""
    fake_solari = FakeSolari()
    monkeypatch.setattr("bench.control_plane.runner.SolariClient",
                        SimpleNamespace(from_env=lambda **kw: fake_solari))

    class PassQuarantine:
        def __init__(self, *a, **k): ...
        def run(self, spec):
            return SimpleNamespace(passed=True, merged=True, skipped=False, checks=[],
                                   failure=None, to_dict=lambda: {"passed": True, "checks": []})

    monkeypatch.setattr("bench.control_plane.runner.Quarantine",
                        SimpleNamespace(from_env=lambda *a, **k: PassQuarantine()))
    return fake_solari


@override_settings(BENCH_FAKE_LLM=True)
def test_run_goal_end_to_end_fake(patched):
    from bench.control_plane.runner import run_goal

    goal = Goal.objects.create(text="Launch a landing page for a fintech tool")
    run_goal(goal.id)

    goal.refresh_from_db()
    assert goal.status == Goal.Status.DONE

    tasks = list(Task.objects.filter(goal=goal))
    assert len(tasks) == 1
    t = tasks[0]
    assert t.status == Task.Status.DONE
    assert t.capability == "sandbox"
    assert t.result["status"] == "done"
    assert t.review["verdict"] == "ACCEPT"
    assert t.quarantine["passed"] is True

    # a worker agent was hired and dismissed
    assert Agent.objects.filter(kind="worker").count() == 1
    assert Agent.objects.get(kind="worker").status == "dismissed"
    # a dispatch was evaluated and allowed
    d = Dispatch.objects.get(task=t)
    assert d.effect == "ALLOW"
    # a machine row was recorded via on_machine and marked destroyed
    m = Machine.objects.get()
    assert m.id == "sbx_runner_fake" and m.status == "destroyed"


@override_settings(BENCH_FAKE_LLM=True)
def test_run_goal_records_audit_chain(patched):
    from bench.audit import AuditLog
    from bench.control_plane.api.stores import DjangoAuditStore
    from bench.control_plane.runner import run_goal

    goal = Goal.objects.create(text="ship a page")
    run_goal(goal.id)

    log = AuditLog(DjangoAuditStore())
    kinds = [e.kind for e in log.all()]
    assert "task.created" in kinds
    assert "dispatch.evaluated" in kinds
    assert "worker.hired" in kinds and "worker.dismissed" in kinds
    assert "quarantine.result" in kinds
    assert log.verify().ok


@override_settings(BENCH_FAKE_LLM=True)
def test_denied_task_stops(patched, monkeypatch):
    """Force the policy engine to DENY and check the task ends there."""
    from bench.control_plane import runner

    class DenyEngine:
        def evaluate(self, dispatch):
            from bench.policy import Effect
            return SimpleNamespace(
                effect=Effect.DENY, audit=False, blocked=True, requires_approval=False,
                reason="blocked for the test", matched=[],
            )

    monkeypatch.setattr(runner, "build_policy_engine", lambda: DenyEngine())

    goal = Goal.objects.create(text="do something")
    runner.run_goal(goal.id)

    goal.refresh_from_db()
    t = Task.objects.get(goal=goal)
    assert t.status == Task.Status.DENIED
    assert goal.status == Goal.Status.FAILED
    assert Agent.objects.filter(kind="worker").count() == 0   # never hired
