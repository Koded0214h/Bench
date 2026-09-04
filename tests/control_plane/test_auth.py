from __future__ import annotations

import pytest

pytestmark = pytest.mark.django_db


def test_register_returns_tokens_and_user(api):
    r = api.post("/api/auth/register", {"username": "alice", "password": "s3cure-pass-9x"}, format="json")
    assert r.status_code == 201
    body = r.json()
    assert body["user"]["username"] == "alice"
    assert body["access"] and body["refresh"]

    from django.contrib.auth import get_user_model

    assert get_user_model().objects.filter(username="alice").exists()


def test_register_rejects_short_password(api):
    r = api.post("/api/auth/register", {"username": "bob", "password": "short"}, format="json")
    assert r.status_code == 400


def test_register_rejects_duplicate_username(api, user):
    r = api.post("/api/auth/register", {"username": "tester", "password": "another-good-pass"}, format="json")
    assert r.status_code == 400


def test_login_flow_and_me(api, user):
    r = api.post("/api/auth/token", {"username": "tester", "password": "pw-tester-123"}, format="json")
    assert r.status_code == 200
    access = r.json()["access"]

    me = api.get("/api/auth/me", HTTP_AUTHORIZATION=f"Bearer {access}")
    assert me.status_code == 200 and me.json()["username"] == "tester"


def test_me_requires_auth(api):
    assert api.get("/api/auth/me").status_code == 401


def test_token_refresh(api, user):
    pair = api.post("/api/auth/token", {"username": "tester", "password": "pw-tester-123"}, format="json").json()
    r = api.post("/api/auth/token/refresh", {"refresh": pair["refresh"]}, format="json")
    assert r.status_code == 200 and r.json()["access"]


def test_registered_user_only_sees_own_goals(api):
    a = api.post("/api/auth/register", {"username": "amy", "password": "amy-good-pass-1"}, format="json").json()
    b = api.post("/api/auth/register", {"username": "ben", "password": "ben-good-pass-1"}, format="json").json()

    api.post("/api/goals/", {"text": "amy's goal here", "run": False}, format="json",
             HTTP_AUTHORIZATION=f"Bearer {a['access']}")

    amy_goals = api.get("/api/goals/", HTTP_AUTHORIZATION=f"Bearer {a['access']}").json()
    ben_goals = api.get("/api/goals/", HTTP_AUTHORIZATION=f"Bearer {b['access']}").json()
    assert amy_goals["count"] == 1 and ben_goals["count"] == 0
