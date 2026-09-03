"""Bench's client for Solari — the compute layer workers run on.

Module 1 of Bench. A synchronous facade over the official Solari SDKs
(``solari-sandbox``, ``solari-desktop``, ``solari-browser``). Everything else in
Bench (policy, agents, quarantine, orchestration) touches Solari only through
:class:`SolariClient`. See ``src/bench/solari/README.md``.
"""

from __future__ import annotations

from .backends import SolariBackends
from .client import SolariClient
from .config import SolariConfig
from .errors import (
    ANY_SOLARI_ERROR,
    ActionError,
    AuthError,
    BenchSolariError,
    BrowserSolariError,
    ConcurrencyLimitError,
    GatewayError,
    MachineLaunchError,
    NoCapacityError,
    PlanError,
    SolariConfigError,
    VMSolariError,
    VMTimeoutError,
)
from .handles import BrowserHandle, DesktopHandle, MachineKind, SandboxHandle

__all__ = [
    "SolariClient",
    "SolariConfig",
    "SolariBackends",
    "MachineKind",
    "SandboxHandle",
    "DesktopHandle",
    "BrowserHandle",
    "BenchSolariError",
    "SolariConfigError",
    "MachineLaunchError",
    "ANY_SOLARI_ERROR",
    "VMSolariError",
    "VMTimeoutError",
    "BrowserSolariError",
    "GatewayError",
    "AuthError",
    "PlanError",
    "ConcurrencyLimitError",
    "NoCapacityError",
    "ActionError",
]
