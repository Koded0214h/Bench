"""Errors for ``bench.solari``.

Two kinds:

* Errors Bench raises itself — configuration problems and launch timeouts —
  rooted at :class:`BenchSolariError`.
* Errors from the underlying Solari SDKs, re-exported here so callers have a
  single import site. Note the SDKs ship *two* unrelated ``SolariError``
  classes: ``solari_core`` (sandbox + desktop) and ``solari_browser``. Both are
  re-exported under distinct names, and :data:`ANY_SOLARI_ERROR` is a tuple you
  can pass straight to ``except``.
"""

from __future__ import annotations

from solari_browser.errors import SolariError as BrowserSolariError
from solari_core.errors import (
    ActionError,
    AuthError,
    ConcurrencyLimitError,
    GatewayError,
    NoCapacityError,
    PlanError,
)
from solari_core.errors import SolariError as VMSolariError
from solari_core.errors import TimeoutError as VMTimeoutError


class BenchSolariError(Exception):
    """Base for errors raised by ``bench.solari`` itself (not the SDKs)."""


class SolariConfigError(BenchSolariError):
    """Configuration is missing or invalid (e.g. no API key)."""


class MachineLaunchError(BenchSolariError):
    """A machine was created but never became usable within the launch window."""

    def __init__(self, message: str, *, machine_id: str | None = None, kind: str | None = None) -> None:
        super().__init__(message)
        self.machine_id = machine_id
        self.kind = kind


#: Everything catchable as "a Solari failure", SDK or ours.
ANY_SOLARI_ERROR = (BenchSolariError, VMSolariError, BrowserSolariError)

__all__ = [
    "BenchSolariError",
    "SolariConfigError",
    "MachineLaunchError",
    "ANY_SOLARI_ERROR",
    # re-exports
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
