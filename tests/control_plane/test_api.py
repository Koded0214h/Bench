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


def test_all_reads_require_auth(api):
    for path in ("/api/goals/", "/api/tasks/", "/api/agents/", "/api/spend", "/api/audit"):
        assert api.get(path).status_code == 401, path


def test_create_goal_sets_owner(auth_api, user):
    r = auth_api.post("/api/goals/", {"text": "Launch a landing page", "run": False}, format="json")
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "pending" and body["owner"] == user.username
    assert Goal.objects.get(pk=body["id"]).owner_id == user.id


def test_goals_are_scoped_to_owner(auth_api, user, other_user):
    mine = Goal.objects.create(text="mine", owner=user)
    Goal.objects.create(text="theirs", owner=other_user)

    listed = auth_api.get("/api/goals/").json()
    assert listed["count"] == 1 and listed["results"][0]["id"] == mine.id

    # cannot fetch another user's goal
    theirs_id = Goal.objects.get(text="theirs").id
    assert auth_api.get(f"/api/goals/{theirs_id}/").status_code == 404


def test_tasks_and_children_are_scoped(auth_api, user, other_user):
    g1 = Goal.objects.create(text="a", owner=user)
    g2 = Goal.objects.create(text="b", owner=other_user)
    t1 = Task.objects.create(goal=g1, title="t1", capability="sandbox", status="done")
    t2 = Task.objects.create(goal=g2, title="t2", capability="sandbox", status="done")
    a1 = Agent.objects.create(kind="worker", role="engineering", task=t1)
    Agent.objects.create(kind="worker", role="ops", task=t2)
    Machine.objects.create(id="m1", kind="sandbox", status="ready", agent=a1, task=t1)
    Machine.objects.create(id="m2", kind="sandbox", status="ready", task=t2)
    Dispatch.objects.create(task=t1, capability="sandbox", effect="ALLOW")
    Dispatch.objects.create(task=t2, capability="sandbox", effect="ALLOW")

    assert auth_api.get("/api/tasks/").json()["count"] == 1
    assert auth_api.get("/api/agents/").json()["count"] == 1
    assert auth_api.get("/api/machines/").json()["count"] == 1
    assert auth_api.get("/api/dispatches/").json()["count"] == 1


def test_spend_is_scoped(auth_api, user, other_user):
    mine = Goal.objects.create(text="a", owner=user)
    theirs = Goal.objects.create(text="b", owner=other_user)
    tm = Task.objects.create(goal=mine, title="t", capability="sandbox")
    tt = Task.objects.create(goal=theirs, title="t", capability="sandbox")
    Charge.objects.create(charge_id="c1", ts="t", task_id=tm.id, category="llm", amount_usd=0.20)
    Charge.objects.create(charge_id="c2", ts="t", task_id=tt.id, category="llm", amount_usd=9.00)

    body = auth_api.get("/api/spend").json()
    assert body["total_usd"] == pytest.approx(0.20)
    assert tt.id not in body["tasks"]


def test_audit_is_scoped(auth_api, user, other_user):
    from bench.audit import AuditLog
    from bench.control_plane.api.stores import DjangoAuditStore

    mine = Goal.objects.create(text="a", owner=user)
    theirs = Goal.objects.create(text="b", owner=other_user)
    tm = Task.objects.create(goal=mine, title="t", capability="sandbox")
    tt = Task.objects.create(goal=theirs, title="t", capability="sandbox")

    log = AuditLog(DjangoAuditStore())
    log.note("mine", task_id=tm.id)
    log.note("theirs", task_id=tt.id)

    r = auth_api.get("/api/audit").json()
    assert r["count"] == 1 and r["events"][0]["task_id"] == tm.id
    # chain check stays global
    assert auth_api.get("/api/audit/verify").json()["ok"] is True


def test_escalation_resolve_scoped_and_conflict(auth_api, user, other_user):
    g = Goal.objects.create(text="x", owner=user)
    t = Task.objects.create(goal=g, title="t", capability="browser", status="escalated")
    esc = Escalation.objects.create(task=t, reason="crm write")

    # another user's escalation is invisible
    g2 = Goal.objects.create(text="y", owner=other_user)
    t2 = Task.objects.create(goal=g2, title="t", capability="browser", status="escalated")
    esc2 = Escalation.objects.create(task=t2, reason="theirs")
    assert auth_api.post(f"/api/escalations/{esc2.id}/resolve/", {"approved": False}, format="json").status_code == 404

    r = auth_api.post(f"/api/escalations/{esc.id}/resolve/", {"approved": False}, format="json")
    assert r.status_code == 200
    esc.refresh_from_db(); t.refresh_from_db()
    assert esc.status == "rejected" and t.status == "rejected"
    assert auth_api.post(f"/api/escalations/{esc.id}/resolve/", {"approved": True}, format="json").status_code == 409


def test_policy_rules_listed_for_authed_user(auth_api, api):
    from bench.control_plane.api.models import PolicyRule

    PolicyRule.objects.create(name="deny-x", match={"capability": "browser"}, effect="DENY", priority=0)
    assert auth_api.get("/api/policy/rules/").json()["count"] == 1
    assert api.get("/api/policy/rules/").status_code == 401
