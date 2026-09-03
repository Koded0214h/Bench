"""Deciding whether a single rule matches a single dispatch.

A rule's ``match`` is a mapping of key -> expected. Every entry must match for
the rule to fire. An expected value is a scalar (equality) or a list (membership,
"any of"). Two keys get special treatment:

* ``domain`` — matches the host itself or any subdomain of it. ``salesforce.com``
  matches ``na1.salesforce.com``; a leading ``*.`` is accepted and ignored.
* booleans (e.g. ``stealth``) — compared as booleans, so ``stealth: true`` in a
  rule matches a dispatch with ``stealth=True``.

A key the dispatch has no value for never matches — a rule cannot fire on an
absent field.
"""

from __future__ import annotations

from typing import Any

from .models import Dispatch, Rule

_TRUE = {"true", "1", "yes", "on"}
_FALSE = {"false", "0", "no", "off", ""}


def rule_matches(rule: Rule, dispatch: Dispatch) -> bool:
    return all(_field_matches(key, expected, dispatch) for key, expected in rule.match.items())


def _field_matches(key: str, expected: Any, dispatch: Dispatch) -> bool:
    actual = dispatch.get(key)
    if actual is None:
        return False
    options = expected if isinstance(expected, (list, tuple, set)) else [expected]
    if key == "domain":
        return any(_domain_matches(str(actual), o) for o in options)
    return any(_scalar_eq(actual, o) for o in options)


def _domain_matches(host: str, pattern: Any) -> bool:
    host = host.strip().lower()
    if host.startswith("www."):
        host = host[4:]
    pat = str(pattern).strip().lower()
    if pat.startswith("*."):
        pat = pat[2:]
    return bool(pat) and (host == pat or host.endswith("." + pat))


def _scalar_eq(actual: Any, expected: Any) -> bool:
    if isinstance(actual, bool) or isinstance(expected, bool):
        return bool(actual) is _to_bool(expected)
    return str(actual).strip().lower() == str(expected).strip().lower()


def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in _TRUE:
        return True
    if text in _FALSE:
        return False
    return bool(value)


__all__ = ["rule_matches"]
