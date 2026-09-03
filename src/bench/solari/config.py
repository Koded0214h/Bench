"""Client configuration, resolved from explicit args or the environment."""

from __future__ import annotations

import os
from dataclasses import dataclass

from .errors import SolariConfigError

# Solari's HTTP gateway. The browser SDK is additionally region-routed; when
# base_url is left as the default the browser SDK picks the URL for `region`.
DEFAULT_BASE_URL = "https://api.getsolari.com"
DEFAULT_REGION = "us-west"


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw)
    except ValueError as exc:  # pragma: no cover - defensive
        raise SolariConfigError(f"{name} must be a number, got {raw!r}") from exc


@dataclass(frozen=True)
class SolariConfig:
    """Everything the client needs to talk to Solari.

    Prefer :meth:`from_env` in application code; construct directly in tests.
    """

    api_key: str
    base_url: str = DEFAULT_BASE_URL
    region: str = DEFAULT_REGION
    # Per-RPC timeout handed to sandbox/desktop control channels (ms).
    call_timeout_ms: int = 30_000
    # How long launch() waits for a machine to connect / report healthy.
    launch_timeout_s: float = 120.0
    launch_poll_interval_s: float = 1.0
    # Default rolling idle window for a machine when the caller doesn't set one.
    default_machine_timeout_ms: int = 15 * 60_000

    def __post_init__(self) -> None:
        if not self.api_key or not self.api_key.strip():
            raise SolariConfigError(
                "Solari API key is empty. Set SOLARI_API_KEY or pass api_key=."
            )
        if not self.base_url.startswith(("http://", "https://")):
            raise SolariConfigError(f"base_url must be an http(s) URL, got {self.base_url!r}")
        object.__setattr__(self, "base_url", self.base_url.rstrip("/"))

    @classmethod
    def from_env(cls, **overrides: object) -> "SolariConfig":
        """Build config from ``SOLARI_*`` environment variables.

        Any keyword override wins over the corresponding environment variable.
        """

        values: dict[str, object] = {
            "api_key": os.environ.get("SOLARI_API_KEY", ""),
            "base_url": os.environ.get("SOLARI_BASE_URL", DEFAULT_BASE_URL) or DEFAULT_BASE_URL,
            "region": os.environ.get("SOLARI_REGION", DEFAULT_REGION) or DEFAULT_REGION,
            "call_timeout_ms": int(_env_float("SOLARI_CALL_TIMEOUT_MS", 30_000)),
            "launch_timeout_s": _env_float("SOLARI_LAUNCH_TIMEOUT_S", 120.0),
        }
        values.update(overrides)
        return cls(**values)  # type: ignore[arg-type]
