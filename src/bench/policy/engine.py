"""Loading rule sets and evaluating dispatches against them."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Iterable

import yaml

from .config import PolicyConfig
from .matching import rule_matches
from .models import Dispatch, Effect, PolicyDecision, Rule, RuleMatch

_DEFAULT_POLICY_PATH = Path(__file__).with_name("default_policy.yaml")


class PolicyError(Exception):
    """Base for policy problems Bench raises."""


class PolicyLoadError(PolicyError):
    """A rule file was unreadable or malformed."""


class PolicyDenied(PolicyError):
    """Raised by :meth:`PolicyEngine.check` when a dispatch is denied."""

    def __init__(self, decision: PolicyDecision) -> None:
        rule = decision.matched[0].name if decision.matched else "default"
        super().__init__(f"dispatch denied by {rule}: {decision.reason}")
        self.decision = decision


class PolicyEscalation(PolicyError):
    """Raised by :meth:`PolicyEngine.check` when a dispatch needs human sign-off."""

    def __init__(self, decision: PolicyDecision) -> None:
        rule = decision.matched[0].name if decision.matched else "default"
        super().__init__(f"dispatch escalated by {rule}: {decision.reason}")
        self.decision = decision


class PolicySet:
    """An ordered collection of rules with unique names."""

    def __init__(self, rules: Iterable[Rule] = ()) -> None:
        self.rules: list[Rule] = list(rules)

    def __len__(self) -> int:
        return len(self.rules)

    def __iter__(self):
        return iter(self.rules)

    def add(self, rule: Rule) -> None:
        self.rules.append(rule)

    def extend(self, other: Iterable[Rule]) -> "PolicySet":
        self.rules.extend(other)
        return self

    def validate(self) -> "PolicySet":
        seen: set[str] = set()
        for rule in self.rules:
            if rule.name in seen:
                raise PolicyLoadError(f"duplicate rule name: {rule.name!r}")
            seen.add(rule.name)
        return self

    # -- construction ------------------------------------------------------

    @classmethod
    def from_dicts(cls, items: Iterable[dict[str, Any]]) -> "PolicySet":
        return cls(Rule.from_dict(item) for item in items)

    @classmethod
    def from_yaml(cls, text: str) -> "PolicySet":
        try:
            data = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            raise PolicyLoadError(f"invalid YAML: {exc}") from exc
        return cls._from_parsed(data, source="<string>")

    @classmethod
    def from_file(cls, path: str | os.PathLike[str]) -> "PolicySet":
        p = Path(path)
        try:
            text = p.read_text(encoding="utf-8")
        except OSError as exc:
            raise PolicyLoadError(f"cannot read policy file {p}: {exc}") from exc
        try:
            data = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            raise PolicyLoadError(f"invalid YAML in {p}: {exc}") from exc
        return cls._from_parsed(data, source=str(p))

    @classmethod
    def from_paths(cls, paths: Iterable[str | os.PathLike[str]]) -> "PolicySet":
        """Load and concatenate a list of YAML files and/or directories.

        Directories contribute their ``*.yaml`` / ``*.yml`` files in sorted order.
        """

        merged = cls()
        for entry in paths:
            p = Path(entry)
            if p.is_dir():
                files = sorted(f for ext in ("*.yaml", "*.yml") for f in p.glob(ext))
                if not files:
                    raise PolicyLoadError(f"no .yaml files in policy directory {p}")
                for f in files:
                    merged.extend(cls.from_file(f))
            else:
                merged.extend(cls.from_file(p))
        return merged

    @classmethod
    def _from_parsed(cls, data: Any, *, source: str) -> "PolicySet":
        if data is None:
            return cls()
        if isinstance(data, dict):
            items = data.get("rules")
            if items is None:
                raise PolicyLoadError(f"{source}: mapping form must have a 'rules' key")
        elif isinstance(data, list):
            items = data
        else:
            raise PolicyLoadError(f"{source}: expected a list of rules or a mapping with 'rules'")
        if not isinstance(items, list):
            raise PolicyLoadError(f"{source}: 'rules' must be a list")
        try:
            return cls.from_dicts(items)
        except ValueError as exc:
            raise PolicyLoadError(f"{source}: {exc}") from exc


class PolicyEngine:
    """Evaluate dispatches against a rule set with a configured default effect."""

    def __init__(self, policy_set: PolicySet, *, default_effect: Effect = Effect.DENY) -> None:
        self.policy_set = policy_set.validate()
        self.default_effect = default_effect

    # -- construction ------------------------------------------------------

    @classmethod
    def from_config(cls, config: PolicyConfig) -> "PolicyEngine":
        rules = PolicySet()
        if not config.disable_defaults:
            rules.extend(PolicySet.from_file(_DEFAULT_POLICY_PATH))
        if config.rule_paths:
            rules.extend(PolicySet.from_paths(config.rule_paths))
        return cls(rules, default_effect=config.default_effect)

    @classmethod
    def from_env(cls, **overrides: object) -> "PolicyEngine":
        return cls.from_config(PolicyConfig.from_env(**overrides))

    # -- evaluation ------------------------------------------------------

    def evaluate(self, dispatch: Dispatch) -> PolicyDecision:
        matched = [
            RuleMatch(r.name, r.effect, r.reason)
            for r in self.policy_set
            if r.enabled and rule_matches(r, dispatch)
        ]
        audit = any(m.effect is Effect.AUDIT for m in matched)

        for tier in (Effect.DENY, Effect.ESCALATE, Effect.ALLOW, Effect.AUDIT):
            hit = next((m for m in matched if m.effect is tier), None)
            if hit is None:
                continue
            effect = Effect.ALLOW if tier is Effect.AUDIT else tier
            return PolicyDecision(
                effect=effect,
                audit=audit,
                reason=hit.reason,
                matched=tuple(matched),
                default_applied=False,
            )

        # No decisive rule matched — fall back to the configured default.
        if self.default_effect is Effect.AUDIT:
            return PolicyDecision(
                effect=Effect.ALLOW,
                audit=True,
                reason="default effect AUDIT: no rule matched",
                matched=tuple(matched),
                default_applied=True,
            )
        return PolicyDecision(
            effect=Effect.DENY,
            audit=audit,
            reason="default effect DENY: no rule matched",
            matched=tuple(matched),
            default_applied=True,
        )

    def check(self, dispatch: Dispatch) -> PolicyDecision:
        """Evaluate and raise unless the dispatch is allowed.

        Raises :class:`PolicyDenied` for DENY, :class:`PolicyEscalation` for
        ESCALATE. Returns the decision (with ``.audit`` possibly set) otherwise.
        """

        decision = self.evaluate(dispatch)
        if decision.blocked:
            raise PolicyDenied(decision)
        if decision.requires_approval:
            raise PolicyEscalation(decision)
        return decision


__all__ = [
    "PolicySet",
    "PolicyEngine",
    "PolicyError",
    "PolicyLoadError",
    "PolicyDenied",
    "PolicyEscalation",
]
