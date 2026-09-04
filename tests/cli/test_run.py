from __future__ import annotations

import pytest

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _no_dotenv(monkeypatch):
    # isolate the CLI from the repo's real .env
    monkeypatch.setattr("bench.run.__main__.load_dotenv", lambda *a, **k: None)


@pytest.fixture
def no_keys(monkeypatch):
    monkeypatch.delenv("SOLARI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)


def test_requires_solari_key(no_keys, capsys):
    from bench.run.__main__ import main

    assert main(["some goal"]) == 2
    assert "SOLARI_API_KEY" in capsys.readouterr().out


def test_real_mode_requires_anthropic_key(monkeypatch, capsys):
    monkeypatch.setenv("SOLARI_API_KEY", "slr_live_x")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    from bench.run.__main__ import main

    assert main(["some goal"]) == 2
    assert "ANTHROPIC_API_KEY" in capsys.readouterr().out


def test_fake_mode_creates_goal_and_runs(monkeypatch, capsys):
    monkeypatch.setenv("SOLARI_API_KEY", "slr_live_x")
    calls = {}

    def fake_run_goal(goal_id, *, sink_factory=None):
        from bench.control_plane.api.models import Goal

        calls["goal_id"] = goal_id
        calls["sink_factory"] = sink_factory
        g = Goal.objects.get(pk=goal_id)
        g.status = Goal.Status.DONE
        g.save(update_fields=["status"])

    monkeypatch.setattr("bench.control_plane.runner.run_goal", fake_run_goal)

    from bench.run.__main__ import main

    rc = main(["--fake", "Launch", "a", "landing", "page"])
    assert rc == 0

    import os
    assert os.environ["BENCH_FAKE_LLM"] == "true"

    from bench.control_plane.api.models import Goal

    goal = Goal.objects.get(pk=calls["goal_id"])
    assert goal.text == "Launch a landing page"
    assert goal.status == "done"

    out = capsys.readouterr().out
    assert "DONE" in out and "/live" in out


def test_budget_and_retries_flags_set_env(monkeypatch):
    monkeypatch.setenv("SOLARI_API_KEY", "slr_live_x")
    monkeypatch.setattr("bench.control_plane.runner.run_goal", lambda gid, **kw: None)

    from bench.run.__main__ import main

    main(["--fake", "--budget", "3.5", "--retries", "4", "--max-workers", "7", "goal"])
    import os
    assert os.environ["BENCH_TASK_BUDGET_USD"] == "3.5"
    assert os.environ["BENCH_RETRY_LIMIT"] == "4"
    assert os.environ["BENCH_MAX_WORKERS"] == "7"
