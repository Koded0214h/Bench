"""Data types for the policy engine.

A :class:`Dispatch` describes a worker the orchestrator is about to hire. A
:class:`Rule` matches some dispatches and assigns an :class:`Effect`. Evaluating
every rule against a dispatch yields a :class:`PolicyDecision`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from urllib.parse import urlsplit


class Effect(str, Enum):
    ALLOW = "ALLOW"        # permit the dispatch
    DENY = "DENY"          # block it, no machine is allocated
    ESCALATE = "ESCALATE"  # block pending human sign-off
    AUDIT = "AUDIT"        # permit, but flag the dispatch for the audit trail

    @classmethod
    def parse(cls, value: Any) -> "Effect":
        if isinstance(value, cls):
            return value
        try:
            return cls(str(value).strip().upper())
        except ValueError as exc:  # pragma: no cover - defensive
            raise ValueError(
                f"unknown effect {value!r}; expected one of {[e.value for e in cls]}"
            ) from exc


# Precedence when several rules match: the first tier with a hit wins.
# DENY beats ESCALATE beats ALLOW beats AUDIT. AUDIT resolves to an allow.
PRECEDENCE = (Effect.DENY, Effect.ESCALATE, Effect.ALLOW, Effect.AUDIT)

# Fields a rule's ``match`` block can name directly; anything else is looked up
# in ``Dispatch.metadata``.
DISPATCH_FIELDS = frozenset(
    {"capability", "action", "domain", "url", "network", "tool", "agent", "task_id", "stealth", "purpose"}
)


@dataclass
class Dispatch:
    """The thing being policy-checked: one worker, one capability, one job."""

    capability: str
    action: str | None = None          # e.g. "read" | "write"
    domain: str | None = None          # target host, for browser work
    url: str | None = None             # full target URL; domain is derived if unset
    network: str | None = None         # e.g. "external" | "internal" | "none"
    tool: str | None = None            # e.g. "salesforce"
    agent: str | None = None           # hiring agent / role, e.g. "ops"
    task_id: str | None = None
    stealth: bool = False              # stealth browsing does not exempt from policy
    purpose: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.capability = str(self.capability).strip().lower()
        if self.domain is None and self.url:
            host = urlsplit(self.url if "//" in self.url else f"//{self.url}").hostname
            if host:
                self.domain = host
        if self.domain:
            self.domain = self.domain.strip().lower()

    def get(self, key: str) -> Any:
        """Resolve a match key against a named field, then ``metadata``."""

        if key in DISPATCH_FIELDS:
            return getattr(self, key)
        return self.metadata.get(key)


@dataclass(frozen=True)
class Rule:
    name: str
    match: dict[str, Any]
    effect: Effect
    reason: str | None = None
    enabled: bool = True

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Rule":
        missing = {"name", "match", "effect"} - data.keys()
        if missing:
            raise ValueError(f"rule is missing required key(s): {sorted(missing)}")
        match = data["match"]
        if not isinstance(match, dict) or not match:
            raise ValueError(f"rule {data['name']!r}: 'match' must be a non-empty mapping")
        return cls(
            name=str(data["name"]),
            match=dict(match),
            effect=Effect.parse(data["effect"]),
            reason=data.get("reason"),
            enabled=bool(data.get("enabled", True)),
        )


@dataclass(frozen=True)
class RuleMatch:
    """A rule that fired during evaluation."""

    name: str
    effect: Effect
    reason: str | None = None


@dataclass(frozen=True)
class PolicyDecision:
    effect: Effect                      # final: ALLOW | DENY | ESCALATE
    audit: bool                         # an AUDIT rule fired, or default effect is AUDIT
    reason: str | None
    matched: tuple[RuleMatch, ...]
    default_applied: bool               # no decisive rule matched; the default was used

    @property
    def allowed(self) -> bool:
        return self.effect is Effect.ALLOW

    @property
    def blocked(self) -> bool:
        return self.effect is Effect.DENY

    @property
    def requires_approval(self) -> bool:
        return self.effect is Effect.ESCALATE

    def to_dict(self) -> dict[str, Any]:
        return {
            "effect": self.effect.value,
            "audit": self.audit,
            "reason": self.reason,
            "default_applied": self.default_applied,
            "matched": [
                {"name": m.name, "effect": m.effect.value, "reason": m.reason} for m in self.matched
            ],
        }


__all__ = [
    "Effect",
    "Dispatch",
    "Rule",
    "RuleMatch",
    "PolicyDecision",
    "DISPATCH_FIELDS",
    "PRECEDENCE",
]
