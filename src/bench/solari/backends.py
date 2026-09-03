"""Factory seam for the three underlying Solari SDK clients.

Real code uses the defaults. Tests pass a :class:`SolariBackends` with fakes so
the facade can be exercised without touching the network.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from .config import DEFAULT_BASE_URL, SolariConfig

ClientFactory = Callable[[SolariConfig], Any]


def _default_sandbox(cfg: SolariConfig) -> Any:
    from solari_sandbox import SandboxClient

    return SandboxClient(
        api_key=cfg.api_key, base_url=cfg.base_url, call_timeout_ms=cfg.call_timeout_ms
    )


def _default_desktop(cfg: SolariConfig) -> Any:
    from solari_desktop import DesktopClient

    return DesktopClient(
        api_key=cfg.api_key, base_url=cfg.base_url, call_timeout_ms=cfg.call_timeout_ms
    )


def _default_browser(cfg: SolariConfig) -> Any:
    from solari_browser import Solari

    kwargs: dict[str, Any] = {"api_key": cfg.api_key, "region": cfg.region}
    # The browser SDK is region-routed; only force base_url when the caller set
    # a non-default one (staging / self-hosted gateway).
    if cfg.base_url and cfg.base_url != DEFAULT_BASE_URL:
        kwargs["base_url"] = cfg.base_url
    return Solari(**kwargs)


@dataclass
class SolariBackends:
    sandbox: ClientFactory = field(default=_default_sandbox)
    desktop: ClientFactory = field(default=_default_desktop)
    browser: ClientFactory = field(default=_default_browser)
