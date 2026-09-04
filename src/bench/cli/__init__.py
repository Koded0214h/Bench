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


def llm_is_configured() -> bool:
    """True when some LLM provider can be reached (any known key, or a local
    endpoint / Ollama)."""

    keys = ("ANTHROPIC_API_KEY", "GEMINI_API_KEY", "GROQ_API_KEY", "OPENROUTER_API_KEY",
            "CEREBRAS_API_KEY", "OPENAI_API_KEY", "BENCH_LLM_API_KEY")
    if any(os.environ.get(k) for k in keys):
        return True
    if os.environ.get("BENCH_LLM_BASE_URL"):
        return True
    return os.environ.get("BENCH_LLM_PROVIDER", "").strip().lower() == "ollama"


def setup_django() -> None:
    import sys

    src = str(REPO_ROOT / "src")
    if src not in sys.path:
        sys.path.insert(0, src)
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "bench.control_plane.settings")
    import django

    django.setup()


__all__ = ["load_dotenv", "setup_django", "llm_is_configured", "REPO_ROOT"]
