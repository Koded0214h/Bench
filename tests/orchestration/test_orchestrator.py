from __future__ import annotations

import pytest

from bench.agents import FakeLLM
from bench.orchestration import Orchestrator, OrchestrationConfig, TaskStatus
from bench.policy import Effect, PolicyEngine, PolicySet
from tests.orchestration.conftest import (
    FakeQuarantine,
    plan_call,
    review_call,
    sandbox_task,
    worker_finish,
)


def make(llm_script, *, policy, meter, audit, solari, quarantine=None, retry_limit=2):
    return Orchestrator(
        llm=FakeLLM(model="claude-sonnet-5", script=llm_script),
        solari=solari, policy=policy, meter=meter, audit=audit,
        quarantine=quarantine or FakeQuarantine(),
        config=OrchestrationConfig(retry_limit=retry_limit),
    )


def test_happy_path_single_task(allow_policy, meter, audit, solari):
    orch = make(
        [plan_call([sandbox_task()]), worker_finish(), review_call("ACCEPT", "meets criteria")],
        policy=allow_policy, meter=meter, audit=audit, solari=solari,
    )
    run = orch.run("Launch a landing page", goal_id="g1")

    assert run.status == "done" and run.done
    (o,) = run.outcomes
    assert o.status == TaskStatus.DONE and o.accepted and o.attempts == 1
    assert o.worker_result.artifact_urls()
    assert solari.sandboxes[0].closed is True

    kinds = [e.kind for e in audit.all()]
    for k in ("task.created", "dispatch.evaluated", "worker.hired", "machine.launched",
              "machine.destroyed", "worker.dismissed", "quarantine.result", "task.state_changed"):
        assert k in kinds
    assert audit.verify().ok


def test_policy_deny_stops_before_hiring(meter, audit, solari):
    deny = PolicyEngine(PolicySet.from_dicts([
        {"name": "deny-sandbox", "match": {"capability": "sandbox"}, "effect": "DENY", "reason": "no"},
    ]))
    orch = make([plan_call([sandbox_task()])], policy=deny, meter=meter, audit=audit, solari=solari)
    run = orch.run("do it", goal_id="g")

    assert run.status == "blocked"
    (o,) = run.outcomes
    assert o.status == TaskStatus.DENIED and o.blocked
    assert solari.sandboxes == []                      # never launched a machine
    assert "worker.hired" not in [e.kind for e in audit.all()]


def test_policy_escalate_pauses_task(meter, audit, solari):
    esc = PolicyEngine(PolicySet.from_dicts([
        {"name": "esc", "match": {"capability": "sandbox"}, "effect": "ESCALATE", "reason": "sign-off"},
    ]))
    orch = make([plan_call([sandbox_task()])], policy=esc, meter=meter, audit=audit, solari=solari)
    run = orch.run("do it", goal_id="g")

    (o,) = run.outcomes
    assert o.status == TaskStatus.ESCALATED and o.escalation_reason == "sign-off"
    assert run.status == "blocked"
    assert "escalation.raised" in [e.kind for e in audit.all()]


def test_quarantine_fails_then_passes_on_retry(allow_policy, meter, audit, solari):
    orch = make(
        [plan_call([sandbox_task()]),
         worker_finish(summary="attempt 1"),
         worker_finish(summary="attempt 2"),
         review_call("ACCEPT")],
        policy=allow_policy, meter=meter, audit=audit, solari=solari,
        quarantine=FakeQuarantine([False, True]),
    )
    run = orch.run("ship", goal_id="g")

    (o,) = run.outcomes
    assert o.status == TaskStatus.DONE and o.attempts == 2
    assert len(solari.sandboxes) == 2                  # a fresh machine each attempt
    assert audit.verify().ok


def test_retry_budget_exhausted_escalates(allow_policy, meter, audit, solari):
    orch = make(
        [plan_call([sandbox_task()]),
         worker_finish(), worker_finish(), worker_finish()],  # 3 attempts (retry_limit=2)
        policy=allow_policy, meter=meter, audit=audit, solari=solari,
        quarantine=FakeQuarantine([False, False, False]),
        retry_limit=2,
    )
    run = orch.run("ship", goal_id="g")

    (o,) = run.outcomes
    assert o.status == TaskStatus.ESCALATED
    assert "retry budget spent" in o.escalation_reason
    assert o.attempts == 3
    assert run.status == "blocked"


def test_worker_failure_then_success_on_retry(allow_policy, meter, audit, solari):
    orch = make(
        [plan_call([sandbox_task()]),
         worker_finish(status="failed", summary="port in use"),
         worker_finish(status="done"),
         review_call("ACCEPT")],
        policy=allow_policy, meter=meter, audit=audit, solari=solari,
    )
    run = orch.run("ship", goal_id="g")
    (o,) = run.outcomes
    assert o.status == TaskStatus.DONE and o.attempts == 2


def test_review_reject_is_terminal_failed(allow_policy, meter, audit, solari):
    orch = make(
        [plan_call([sandbox_task()]), worker_finish(), review_call("REJECT", "no live URL")],
        policy=allow_policy, meter=meter, audit=audit, solari=solari,
    )
    run = orch.run("ship", goal_id="g")
    (o,) = run.outcomes
    assert o.status == TaskStatus.REJECTED
    assert run.status == "failed"


def test_budget_exceeded_fails_task(allow_policy, audit, solari):
    from bench.metering import Meter

    tight = Meter(task_budget_usd=0.01, max_workers=4)
    tight.charge(task_id="pre", amount_usd=0.0)  # noop
    orch = make(
        [plan_call([sandbox_task()])],
        policy=allow_policy, meter=tight, audit=audit, solari=solari,
    )
    # budget_estimate default 0.10 > 0.01 ceiling -> check_budget raises in `work`
    run = orch.run("ship", goal_id="g")
    (o,) = run.outcomes
    assert o.status == TaskStatus.FAILED and "ceiling" in (o.failure or "")
    assert solari.sandboxes == []


def test_multi_task_plan_runs_in_dependency_order(allow_policy, meter, audit, solari):
    tasks = [
        {"title": "B", "capability": "sandbox", "instructions": "second",
         "success_criteria": ["x"], "depends_on": ["A"]},
        {"title": "A", "capability": "sandbox", "instructions": "first", "success_criteria": ["x"]},
    ]
    orch = make(
        [plan_call(tasks),
         worker_finish(summary="A done"), review_call("ACCEPT"),
         worker_finish(summary="B done"), review_call("ACCEPT")],
        policy=allow_policy, meter=meter, audit=audit, solari=solari,
    )
    run = orch.run("two steps", goal_id="g")
    assert [o.task.title for o in run.outcomes] == ["A", "B"]
    assert all(o.status == TaskStatus.DONE for o in run.outcomes)
    assert run.status == "done"


def test_decompose_failure_is_handled(allow_policy, meter, audit, solari):
    orch = make(["I am not going to call a tool"], policy=allow_policy, meter=meter, audit=audit, solari=solari)
    run = orch.run("do it", goal_id="g")
    assert run.status == "failed" and run.outcomes == []
    assert "task.state_changed" in [e.kind for e in audit.all()]


def test_sink_receives_lifecycle_events(allow_policy, meter, audit, solari):
    calls: list[str] = []

    class RecordingSink:
        def __getattr__(self, name):
            def _rec(*a, **k):
                calls.append(name)
            return _rec

    orch = Orchestrator(
        llm=FakeLLM(model="claude-sonnet-5",
                    script=[plan_call([sandbox_task()]), worker_finish(), review_call("ACCEPT")]),
        solari=solari, policy=allow_policy, meter=meter, audit=audit,
        quarantine=FakeQuarantine(), sink=RecordingSink(),
        config=OrchestrationConfig(retry_limit=1),
    )
    orch.run("ship", goal_id="g")
    for hook in ("on_plan", "on_dispatch", "on_worker_hired", "on_machine",
                 "on_worker_result", "on_quarantine", "on_review", "on_task_status"):
        assert hook in calls
