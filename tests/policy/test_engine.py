from __future__ import annotations

import pytest

from bench.policy import (
    Dispatch,
    Effect,
    PolicyDenied,
    PolicyEngine,
    PolicyEscalation,
    PolicySet,
)

RULES = [
    {"name": "deny-x", "match": {"capability": "browser", "domain": "x.com"}, "effect": "DENY",
     "reason": "no public posting"},
    {"name": "escalate-crm-write", "match": {"capability": "browser", "domain": "salesforce.com", "action": "write"},
     "effect": "ESCALATE", "reason": "human sign-off"},
    {"name": "audit-egress", "match": {"capability": "sandbox", "network": "external"}, "effect": "AUDIT"},
    {"name": "allow-sandbox", "match": {"capability": "sandbox"}, "effect": "ALLOW"},
]


def engine(default=Effect.DENY, rules=RULES) -> PolicyEngine:
    return PolicyEngine(PolicySet.from_dicts(rules), default_effect=default)


def test_deny_rule_blocks():
    d = engine().evaluate(Dispatch(capability="browser", domain="x.com"))
    assert d.effect is Effect.DENY and not d.allowed
    assert d.matched[0].name == "deny-x"


def test_escalate_rule():
    d = engine().evaluate(Dispatch(capability="browser", domain="salesforce.com", action="write"))
    assert d.requires_approval and d.reason == "human sign-off"


def test_allow_rule():
    d = engine().evaluate(Dispatch(capability="sandbox", network="none"))
    assert d.allowed and not d.audit


def test_audit_permits_and_flags():
    d = engine().evaluate(Dispatch(capability="sandbox", network="external"))
    assert d.allowed          # allow-sandbox wins the decisive tier
    assert d.audit            # audit-egress still flags it
    assert {m.name for m in d.matched} == {"audit-egress", "allow-sandbox"}


def test_audit_alone_is_an_allow():
    e = PolicyEngine(PolicySet.from_dicts([RULES[2]]), default_effect=Effect.DENY)
    d = e.evaluate(Dispatch(capability="sandbox", network="external"))
    assert d.allowed and d.audit and not d.default_applied


def test_deny_beats_allow_regardless_of_order():
    rules = [
        {"name": "allow-all-browser", "match": {"capability": "browser"}, "effect": "ALLOW"},
        {"name": "deny-x", "match": {"capability": "browser", "domain": "x.com"}, "effect": "DENY"},
    ]
    d = PolicyEngine(PolicySet.from_dicts(rules)).evaluate(Dispatch(capability="browser", domain="x.com"))
    assert d.effect is Effect.DENY


def test_stealth_does_not_bypass_deny():
    d = engine().evaluate(Dispatch(capability="browser", domain="x.com", stealth=True))
    assert d.effect is Effect.DENY


def test_default_deny_when_no_match():
    d = engine().evaluate(Dispatch(capability="browser", domain="unknown.example"))
    assert d.effect is Effect.DENY and d.default_applied
    assert "default effect DENY" in d.reason


def test_default_audit_allows_unmatched():
    d = engine(default=Effect.AUDIT).evaluate(Dispatch(capability="browser", domain="unknown.example"))
    assert d.allowed and d.audit and d.default_applied


def test_check_raises_on_deny():
    with pytest.raises(PolicyDenied) as ei:
        engine().check(Dispatch(capability="browser", domain="x.com"))
    assert ei.value.decision.effect is Effect.DENY


def test_check_raises_on_escalate():
    with pytest.raises(PolicyEscalation):
        engine().check(Dispatch(capability="browser", domain="salesforce.com", action="write"))


def test_check_returns_decision_on_allow():
    decision = engine().check(Dispatch(capability="sandbox", network="external"))
    assert decision.allowed and decision.audit


def test_disabled_rule_is_skipped():
    rules = [{"name": "deny-x", "match": {"capability": "browser", "domain": "x.com"},
              "effect": "DENY", "enabled": False}]
    d = PolicyEngine(PolicySet.from_dicts(rules), default_effect=Effect.AUDIT).evaluate(
        Dispatch(capability="browser", domain="x.com")
    )
    assert d.allowed


def test_decision_to_dict_round_trips():
    d = engine().evaluate(Dispatch(capability="browser", domain="x.com"))
    payload = d.to_dict()
    assert payload["effect"] == "DENY"
    assert payload["matched"][0]["name"] == "deny-x"
