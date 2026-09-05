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


def missing_llm_key() -> str | None:
    """The env var the selected provider needs but doesn't have, else None.

    Deliberately narrow: it checks the provider BENCH_PROD (or an explicit pin)
    actually selects, so a stale key for a different provider can't wave a run
    through pre-flight and fail after a machine is already running.
    """

    import sys
    from pathlib import Path

    src = str(Path(__file__).resolve().parents[1])
    if src not in sys.path:
        sys.path.insert(0, src)
    from bench.agents.llm import required_key_var

    var = required_key_var()
    if var is None:
        return None
    return None if os.environ.get(var) else var


def llm_is_configured() -> bool:
    """True when the provider that will actually be used has a usable key."""

    return missing_llm_key() is None


def setup_django() -> None:
    import sys

    src = str(REPO_ROOT / "src")
    if src not in sys.path:
        sys.path.insert(0, src)
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "bench.control_plane.settings")
    import django

    django.setup()


__all__ = ["load_dotenv", "setup_django", "llm_is_configured", "REPO_ROOT"]
