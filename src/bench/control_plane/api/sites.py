"""Serve a completed sandbox task's captured files back as a real static site.

A sandbox worker's own preview_port URL dies the moment its machine is torn
down — before the CEO even reviews it, let alone before a human clicks it
from the dashboard. But every text artifact a worker reports (index.html,
style.css, ...) is already captured permanently into ``task.result`` in the
database (see ``EngineeringWorker._auto_capture`` and the write_file/
export_file tools). This view serves that captured bundle back over HTTP, so
"the live URL" survives for as long as the task record does — no sandbox,
no expiry, no concurrency cost.

Public by design: this is the same kind of shareable link a sandbox's own
preview URL already was (unauthenticated, gated only by an unguessable id),
not a private resource.
"""

from __future__ import annotations

import base64

from django.http import Http404, HttpResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny

from .models import Task

_MIME_BY_EXT = {
    ".html": "text/html; charset=utf-8", ".htm": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8", ".js": "text/javascript; charset=utf-8",
    ".json": "application/json", ".svg": "image/svg+xml", ".txt": "text/plain; charset=utf-8",
    ".md": "text/plain; charset=utf-8", ".png": "image/png", ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg", ".gif": "image/gif", ".webp": "image/webp", ".ico": "image/x-icon",
    ".woff": "font/woff", ".woff2": "font/woff2",
}


def _guess_mime(path: str, declared: str | None) -> str:
    if declared and declared != "application/octet-stream":
        return declared
    for ext, mime in _MIME_BY_EXT.items():
        if path.lower().endswith(ext):
            return mime
    return "application/octet-stream"


def _file_artifacts(task: Task) -> list[dict]:
    result = task.result or {}
    return [a for a in (result.get("artifacts") or []) if isinstance(a, dict) and a.get("kind") in ("file", "image")]


@api_view(["GET"])
@permission_classes([AllowAny])
def task_site(request, task_id: str, path: str = ""):
    try:
        task = Task.objects.get(pk=task_id)
    except Task.DoesNotExist:
        raise Http404("no such task")

    artifacts = _file_artifacts(task)
    if not artifacts:
        raise Http404("this task captured no files to serve")

    want = path.strip("/") or "index.html"
    match = next((a for a in artifacts if a.get("value", "").strip("/") == want), None)
    if match is None and want == "index.html":
        # no file literally named index.html — fall back to the first html file,
        # since a worker may have named its page something else.
        match = next((a for a in artifacts if a.get("value", "").lower().endswith((".html", ".htm"))), None)
    if match is None:
        raise Http404(f"no captured file matches {want!r}")

    meta = match.get("meta") or {}
    mime = _guess_mime(want, meta.get("mime"))

    if isinstance(meta.get("content"), str):
        return HttpResponse(meta["content"], content_type=mime)
    if isinstance(meta.get("content_b64"), str):
        try:
            raw = base64.b64decode(meta["content_b64"])
        except Exception:  # noqa: BLE001 - corrupt/legacy data, treat as missing
            raise Http404("stored file is unreadable")
        return HttpResponse(raw, content_type=mime)
    raise Http404(f"{want!r} was reported but its content was never captured")
