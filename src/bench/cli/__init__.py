"""Shared CLI helpers — env loading and Django bootstrap."""

from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent


def load_dotenv(path: str | os.PathLike[str] | None = None) -> None:
    """Minimal .env loader: KEY=VALUE per line, no export, no interpolation.
    Existing environment values win."""

    p = Path(path) if path else REPO_ROOT / ".env"
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def setup_django() -> None:
    import sys

    src = str(REPO_ROOT / "src")
    if src not in sys.path:
        sys.path.insert(0, src)
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "bench.control_plane.settings")
    import django

    django.setup()


__all__ = ["load_dotenv", "setup_django", "REPO_ROOT"]
