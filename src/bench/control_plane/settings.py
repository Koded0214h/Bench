"""Django settings for the Bench control plane.

Reads secrets and toggles from the environment. Ships dev-safe defaults; the
Security section of the top-level README lists what to change before this leaves
localhost (SECRET_KEY, DEBUG, PostgreSQL).
"""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlparse

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent  # repo root

# Patchright/Playwright's *sync* API (used by BrowserToolset for ops/research
# workers) leaves the calling thread reporting a "running" asyncio event loop
# for the whole browser session — a quirk of how it bridges sync and async,
# not real concurrent async DB access. Django's async-safety check can't tell
# the difference and refuses every ORM call made on that thread meanwhile
# (e.g. recording LLM spend mid-task), which made every browser-capability
# task fail on its very first step. This is Django's own documented escape
# hatch for exactly this false-positive case — must be set before any ORM
# call happens on a Playwright-poisoned thread, so it goes here at import time.
os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "true")


def _bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


SECRET_KEY = os.environ.get("SECRET_KEY", "dev-insecure-change-me-before-production")
DEBUG = _bool("DEBUG", True)
ALLOWED_HOSTS = (
    ["*"] if DEBUG else [h.strip() for h in os.environ.get("ALLOWED_HOSTS", "").split(",") if h.strip()]
)

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.staticfiles",
    "rest_framework",
    "corsheaders",
    "bench.control_plane.api",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.security.SecurityMiddleware",
]

ROOT_URLCONF = "bench.control_plane.urls"
WSGI_APPLICATION = "bench.control_plane.wsgi.application"
ASGI_APPLICATION = "bench.control_plane.asgi.application"

TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [Path(__file__).resolve().parent / "templates"],
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": []},
}]


def _database() -> dict:
    url = os.environ.get("DATABASE_URL", "").strip()
    if url.startswith(("postgres://", "postgresql://")):
        p = urlparse(url)
        return {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": p.path.lstrip("/"),
            "USER": p.username or "",
            "PASSWORD": p.password or "",
            "HOST": p.hostname or "",
            "PORT": str(p.port or ""),
        }
    default_path = os.environ.get("BENCH_DB_PATH", str(BASE_DIR / ".bench" / "db.sqlite3"))
    Path(default_path).parent.mkdir(parents=True, exist_ok=True)
    return {
        "ENGINE": "django.db.backends.sqlite3", "NAME": default_path,
        # Independent tasks within a goal now run on separate threads, each
        # writing its own task/audit/machine rows — sqlite allows only one
        # writer at a time, and without a busy timeout a second writer gets
        # "database is locked" immediately instead of just waiting its turn.
        "OPTIONS": {"timeout": 20},
        # Django's sqlite test db defaults to a single ":memory:" database
        # implicitly shared across every thread's connection — harmless for
        # sequential tests, but it collides the instant two task threads
        # write at once. A file-backed test db behaves like production:
        # independent connections serialized by sqlite's own (now patient)
        # file lock, instead of one connection object fought over by threads.
        "TEST": {"NAME": str(Path(default_path).with_name("test_" + Path(default_path).name))},
    }


DATABASES = {"default": _database()}

AUTH_PASSWORD_VALIDATORS: list = []
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

import sys as _sys  # noqa: E402

if "pytest" in _sys.modules:  # fast password hashing under the test suite
    PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
USE_TZ = True
TIME_ZONE = "UTC"
LANGUAGE_CODE = "en-us"

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / ".bench" / "static"

# Built React app (frontend/dist), served at /app/ so the whole thing is on :8000.
FRONTEND_DIST = BASE_DIR / "frontend" / "dist"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.LimitOffsetPagination",
    "PAGE_SIZE": 50,
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
}

from datetime import timedelta  # noqa: E402

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=12),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=14),
}

CORS_ALLOW_ALL_ORIGINS = DEBUG
CORS_ALLOWED_ORIGINS = [
    o.strip() for o in os.environ.get("CORS_ALLOWED_ORIGINS", "").split(",") if o.strip()
]

# --- Bench wiring ----------------------------------------------------------
# Run a goal automatically when it is created (POST /api/goals). Off by default
# so tests and the API stay synchronous/predictable; start.sh / the CLI turn it
# on, or POST /api/goals/<id>/run explicitly.
BENCH_AUTORUN = _bool("BENCH_AUTORUN", False)
BENCH_FAKE_LLM = _bool("BENCH_FAKE_LLM", False)
# Shown by the landing page when the demo can't actually run (credits gone).
BENCH_DEMO_PAUSED = _bool("BENCH_DEMO_PAUSED", False)
BENCH_DEMO_NOTICE = os.environ.get("BENCH_DEMO_NOTICE", "").strip()

# Tasks within a goal now run concurrently on real threads (see
# Orchestrator._run_tasks), each writing its own rows, while the dashboard
# polls the API every couple seconds — real simultaneous reads and writes.
# sqlite's default journal mode makes a writer exclude every reader, so that
# combination reliably produces "database is locked" under load; WAL mode
# lets reads proceed alongside a writer instead of queuing behind it. The
# OPTIONS timeout above is what's left to fall back on for true writer-vs-
# writer contention (two task threads committing at the same instant).
if DATABASES["default"]["ENGINE"] == "django.db.backends.sqlite3":
    from django.db.backends.signals import connection_created  # noqa: E402

    def _enable_sqlite_wal(sender, connection, **kwargs):
        if connection.vendor == "sqlite":
            connection.cursor().execute("PRAGMA journal_mode=WAL;")

    connection_created.connect(_enable_sqlite_wal)
