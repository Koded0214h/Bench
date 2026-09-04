from __future__ import annotations

import pytest

from bench.control_plane.api.models import (
    Agent,
    Charge,
    Dispatch,
    Escalation,
    Goal,
    Machine,
    Task,
)

pytestmark = pytest.mark.django_db


def test_healthz_is_public(api):
    r = api.get("/healthz")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_create_goal_without_run(auth_api):
    r = auth_api.post("/api/goals/", {"text": "Launch a landing page", "run": False}, format="json")
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "pending" and body["text"] == "Launch a landing page"
    assert Goal.objects.count() == 1


def test_goal_list_and_detail_are_readable_without_auth(api):
    g = Goal.objects.create(text="x")
    Task.objects.create(goal=g, title="t", capability="sandbox", success_criteria=["a"])
    assert api.get("/api/goals/").status_code == 200
    detail = api.get(f"/api/goals/{g.id}/").json()
    assert len(detail["tasks"]) == 1


def test_tasks_filter_by_goal_and_status(api):
    g1, g2 = Goal.objects.create(text="a"), Goal.objects.create(text="b")
    Task.objects.create(goal=g1, title="t1", capability="sandbox", status="done")
    Task.objects.create(goal=g1, title="t2", capability="browser", status="failed")
    Task.objects.create(goal=g2, title="t3", capability="sandbox", status="done")

    assert api.get(f"/api/tasks/?goal={g1.id}").json()["count"] == 2
    assert api.get("/api/tasks/?status=done").json()["count"] == 2


def test_agents_and_machines_live_filters(api):
    g = Goal.objects.create(text="x")
    t = Task.objects.create(goal=g, title="t", capability="sandbox")
    a1 = Agent.objects.create(kind="worker", role="engineering", task=t)
    Agent.objects.create(kind="worker", role="ops", status="dismissed", task=t)
    Machine.objects.create(id="m1", kind="sandbox", status="ready", agent=a1, task=t)
    Machine.objects.create(id="m2", kind="sandbox", status="destroyed", task=t)

    assert api.get("/api/agents/?active=1").json()["count"] == 1
    assert api.get("/api/machines/?live=1").json()["count"] == 1
    assert api.get("/api/machines/").json()["count"] == 2


def test_spend_endpoint_aggregates(api):
    Charge.objects.create(charge_id="c1", ts="t", task_id="t1", category="llm", amount_usd=0.20)
    Charge.objects.create(charge_id="c2", ts="t", task_id="t1", category="machine_time", amount_usd=0.05)
    Charge.objects.create(charge_id="c3", ts="t", task_id="t2", category="llm", amount_usd=1.00)
    body = api.get("/api/spend").json()
    assert body["total_usd"] == pytest.approx(1.25)
    assert body["tasks"]["t1"]["total_usd"] == pytest.approx(0.25)
    assert body["tasks"]["t1"]["by_category"]["llm"] == pytest.approx(0.20)


def test_audit_endpoint_and_verify(api):
    from bench.audit import AuditLog
    from bench.control_plane.api.stores import DjangoAuditStore

    log = AuditLog(DjangoAuditStore())
    log.task_created(task_id="t1", goal="g")
    log.note("hi", task_id="t1")
    log.note("elsewhere", task_id="t2")

    r = api.get("/api/audit?task=t1").json()
    assert r["count"] == 2
    assert api.get("/api/audit/verify").json()["ok"] is True


def test_escalation_resolve_requires_pending(auth_api):
    g = Goal.objects.create(text="x")
    t = Task.objects.create(goal=g, title="t", capability="browser", status="escalated")
    esc = Escalation.objects.create(task=t, reason="crm write")

    r = auth_api.post(f"/api/escalations/{esc.id}/resolve/", {"approved": False}, format="json")
    assert r.status_code == 200
    esc.refresh_from_db(); t.refresh_from_db()
    assert esc.status == "rejected" and t.status == "rejected"

    # second resolve is a conflict
    r2 = auth_api.post(f"/api/escalations/{esc.id}/resolve/", {"approved": True}, format="json")
    assert r2.status_code == 409


def test_write_endpoints_require_auth(api):
    r = api.post("/api/goals/", {"text": "x"}, format="json")
    assert r.status_code in (401, 403)


def test_policy_rules_listed(api):
    from bench.control_plane.api.models import PolicyRule

    PolicyRule.objects.create(name="deny-x", match={"capability": "browser"}, effect="DENY", priority=0)
    assert api.get("/api/policy/rules/").json()["count"] == 1


def test_live_view_renders(api):
    r = api.get("/live")
    assert r.status_code == 200 and b"BENCH" in r.content
