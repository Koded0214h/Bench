"""Bench policy engine — module 2.

The gate before hiring: no worker is spawned until its dispatch passes here.
Rules are declarative YAML, evaluated per dispatch, with four effects —
``ALLOW``, ``DENY``, ``AUDIT``, ``ESCALATE``.

    from bench.policy import PolicyEngine, Dispatch

    engine = PolicyEngine.from_env()
    decision = engine.evaluate(Dispatch(capability="browser", domain="x.com", action="write"))
    if not decision.allowed:
        ...  # denied / escalated — no machine is allocated
"""

from __future__ import annotations

from .config import PolicyConfig, PolicyConfigError
from .engine import (
    PolicyDenied,
    PolicyEngine,
    PolicyError,
    PolicyEscalation,
    PolicyLoadError,
    PolicySet,
)
from .models import Dispatch, Effect, PolicyDecision, Rule, RuleMatch

__all__ = [
    "PolicyEngine",
    "PolicySet",
    "PolicyConfig",
    "Dispatch",
    "Effect",
    "Rule",
    "RuleMatch",
    "PolicyDecision",
    "PolicyError",
    "PolicyConfigError",
    "PolicyLoadError",
    "PolicyDenied",
    "PolicyEscalation",
]
