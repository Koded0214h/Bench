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
    return {"ENGINE": "django.db.backends.sqlite3", "NAME": default_path}


DATABASES = {"default": _database()}

AUTH_PASSWORD_VALIDATORS: list = []
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
USE_TZ = True
TIME_ZONE = "UTC"
LANGUAGE_CODE = "en-us"

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / ".bench" / "static"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticatedOrReadOnly",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.LimitOffsetPagination",
    "PAGE_SIZE": 50,
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
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
