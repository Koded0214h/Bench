from __future__ import annotations

import base64

import pytest

from bench.control_plane.api.models import Goal, Task

pytestmark = pytest.mark.django_db


def _task_with_result(user, result: dict) -> Task:
    goal = Goal.objects.create(text="a landing page", owner=user)
    return Task.objects.create(goal=goal, title="build it", capability="sandbox", status="done", result=result)


def test_serves_index_html_at_bare_task_url(api, user):
    t = _task_with_result(user, {
        "artifacts": [{"kind": "file", "value": "index.html", "meta": {"content": "<h1>hi</h1>"}}],
    })
    r = api.get(f"/sites/{t.id}/")
    assert r.status_code == 200
    assert r["Content-Type"].startswith("text/html")
    assert r.content == b"<h1>hi</h1>"


def test_serves_a_named_asset_alongside_index(api, user):
    t = _task_with_result(user, {
        "artifacts": [
            {"kind": "file", "value": "index.html", "meta": {"content": "<link rel=stylesheet href=style.css>"}},
            {"kind": "file", "value": "style.css", "meta": {"content": "body { color: red }"}},
        ],
    })
    r = api.get(f"/sites/{t.id}/style.css")
    assert r.status_code == 200
    assert r["Content-Type"].startswith("text/css")
    assert b"color: red" in r.content


def test_falls_back_to_any_html_file_when_none_is_named_index(api, user):
    t = _task_with_result(user, {
        "artifacts": [{"kind": "file", "value": "landing.html", "meta": {"content": "<p>ok</p>"}}],
    })
    r = api.get(f"/sites/{t.id}/")
    assert r.status_code == 200
    assert r.content == b"<p>ok</p>"


def test_serves_binary_artifacts_from_base64(api, user):
    png = b"\x89PNGrealbytes"
    t = _task_with_result(user, {
        "artifacts": [
            {"kind": "file", "value": "index.html", "meta": {"content": "<img src=logo.png>"}},
            {"kind": "image", "value": "logo.png", "meta": {"content_b64": base64.b64encode(png).decode(), "mime": "image/png"}},
        ],
    })
    r = api.get(f"/sites/{t.id}/logo.png")
    assert r.status_code == 200
    assert r["Content-Type"] == "image/png"
    assert r.content == png


def test_no_such_task_is_404(api):
    r = api.get("/sites/task_nope/")
    assert r.status_code == 404


def test_task_with_no_result_is_404(api, user):
    goal = Goal.objects.create(text="a", owner=user)
    t = Task.objects.create(goal=goal, title="t", capability="sandbox")
    r = api.get(f"/sites/{t.id}/")
    assert r.status_code == 404


def test_unmatched_path_is_404_not_index(api, user):
    t = _task_with_result(user, {
        "artifacts": [{"kind": "file", "value": "index.html", "meta": {"content": "<h1>hi</h1>"}}],
    })
    r = api.get(f"/sites/{t.id}/does-not-exist.js")
    assert r.status_code == 404


def test_public_no_auth_required(api, user):
    """Same shareability as a sandbox's own preview_port URL — no login needed."""
    t = _task_with_result(user, {
        "artifacts": [{"kind": "file", "value": "index.html", "meta": {"content": "<h1>hi</h1>"}}],
    })
    r = api.get(f"/sites/{t.id}/")  # `api` fixture is unauthenticated
    assert r.status_code == 200
