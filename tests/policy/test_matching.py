from __future__ import annotations

import pytest

from bench.policy import Dispatch, Effect, Rule
from bench.policy.matching import rule_matches


def mk(match: dict) -> Rule:
    return Rule(name="r", match=match, effect=Effect.DENY)


def test_all_keys_must_match():
    d = Dispatch(capability="browser", domain="salesforce.com", action="write")
    assert rule_matches(mk({"capability": "browser", "action": "write"}), d)
    assert not rule_matches(mk({"capability": "browser", "action": "read"}), d)


def test_list_is_membership():
    d = Dispatch(capability="browser", domain="linkedin.com")
    assert rule_matches(mk({"domain": ["x.com", "linkedin.com"]}), d)
    assert not rule_matches(mk({"domain": ["x.com", "reddit.com"]}), d)


def test_absent_field_never_matches():
    d = Dispatch(capability="sandbox")  # no action
    assert not rule_matches(mk({"action": "write"}), d)


def test_domain_matches_subdomains():
    d = Dispatch(capability="browser", domain="na1.salesforce.com")
    assert rule_matches(mk({"domain": "salesforce.com"}), d)


def test_domain_does_not_match_suffix_collision():
    d = Dispatch(capability="browser", domain="notsalesforce.com")
    assert not rule_matches(mk({"domain": "salesforce.com"}), d)


def test_domain_star_prefix_is_ignored():
    d = Dispatch(capability="browser", domain="api.stripe.com")
    assert rule_matches(mk({"domain": "*.stripe.com"}), d)


def test_domain_derived_from_url():
    d = Dispatch(capability="browser", url="https://x.com/compose/post")
    assert d.domain == "x.com"
    assert rule_matches(mk({"domain": "x.com"}), d)


def test_www_prefix_stripped():
    d = Dispatch(capability="browser", domain="www.reddit.com")
    assert rule_matches(mk({"domain": "reddit.com"}), d)


def test_boolean_match():
    d = Dispatch(capability="browser", domain="x.com", stealth=True)
    assert rule_matches(mk({"stealth": True}), d)
    assert not rule_matches(mk({"stealth": False}), d)


def test_metadata_fallback():
    d = Dispatch(capability="sandbox", metadata={"cost_tier": "high"})
    assert rule_matches(mk({"cost_tier": "high"}), d)
    assert not rule_matches(mk({"cost_tier": "low"}), d)


def test_case_insensitive_scalars():
    d = Dispatch(capability="Browser", action="WRITE")
    assert rule_matches(mk({"capability": "browser", "action": "write"}), d)
