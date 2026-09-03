from __future__ import annotations

import pytest

from bench.policy import Dispatch, Effect, PolicyEngine, PolicySet
from bench.policy.config import PolicyConfig, PolicyConfigError
from bench.policy.engine import PolicyLoadError

LIST_YAML = """
- name: deny-x
  match: { capability: browser, domain: x.com }
  effect: DENY
  reason: nope
"""

MAPPING_YAML = """
rules:
  - name: allow-sandbox
    match: { capability: sandbox }
    effect: ALLOW
"""


def test_from_yaml_list_form():
    ps = PolicySet.from_yaml(LIST_YAML)
    assert len(ps) == 1 and ps.rules[0].effect is Effect.DENY


def test_from_yaml_mapping_form():
    ps = PolicySet.from_yaml(MAPPING_YAML)
    assert ps.rules[0].name == "allow-sandbox"


def test_invalid_effect_rejected():
    with pytest.raises(PolicyLoadError):
        PolicySet.from_yaml("- {name: r, match: {capability: sandbox}, effect: MAYBE}")


def test_missing_match_rejected():
    with pytest.raises(PolicyLoadError):
        PolicySet.from_yaml("- {name: r, effect: DENY}")


def test_empty_match_rejected():
    with pytest.raises(PolicyLoadError):
        PolicySet.from_yaml("- {name: r, match: {}, effect: DENY}")


def test_duplicate_names_rejected_on_validate():
    ps = PolicySet.from_yaml(
        "- {name: r, match: {capability: sandbox}, effect: ALLOW}\n"
        "- {name: r, match: {capability: browser}, effect: DENY}"
    )
    with pytest.raises(PolicyLoadError):
        ps.validate()


def test_from_paths_merges_dir(tmp_path):
    (tmp_path / "a.yaml").write_text("- {name: a, match: {capability: sandbox}, effect: ALLOW}")
    (tmp_path / "b.yaml").write_text("- {name: b, match: {capability: browser, domain: x.com}, effect: DENY}")
    ps = PolicySet.from_paths([tmp_path])
    assert {r.name for r in ps} == {"a", "b"}


def test_from_paths_empty_dir_errors(tmp_path):
    with pytest.raises(PolicyLoadError):
        PolicySet.from_paths([tmp_path])


# --- bundled defaults + config ------------------------------------------

def test_default_policy_loads_and_covers_readme_examples():
    engine = PolicyEngine.from_config(PolicyConfig())
    assert engine.evaluate(Dispatch(capability="browser", domain="x.com")).effect is Effect.DENY
    assert engine.evaluate(
        Dispatch(capability="browser", domain="salesforce.com", action="write")
    ).requires_approval
    egress = engine.evaluate(Dispatch(capability="sandbox", network="external"))
    assert egress.allowed and egress.audit


def test_disable_defaults_leaves_empty_set():
    engine = PolicyEngine.from_config(PolicyConfig(disable_defaults=True))
    assert len(engine.policy_set) == 0
    assert engine.evaluate(Dispatch(capability="sandbox")).effect is Effect.DENY


def test_extra_rules_layer_on_top(tmp_path):
    extra = tmp_path / "extra.yaml"
    extra.write_text("- {name: allow-notion, match: {capability: browser, domain: notion.so}, effect: ALLOW}")
    engine = PolicyEngine.from_config(PolicyConfig(rule_paths=(str(extra),)))
    assert engine.evaluate(Dispatch(capability="browser", domain="notion.so")).allowed


def test_config_rejects_allow_default():
    with pytest.raises(PolicyConfigError):
        PolicyConfig(default_effect=Effect.ALLOW)


def test_config_from_env(monkeypatch):
    monkeypatch.setenv("POLICY_DEFAULT_EFFECT", "audit")
    monkeypatch.setenv("POLICY_DISABLE_DEFAULTS", "true")
    cfg = PolicyConfig.from_env()
    assert cfg.default_effect is Effect.AUDIT and cfg.disable_defaults is True
