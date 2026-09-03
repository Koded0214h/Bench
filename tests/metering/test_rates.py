from __future__ import annotations

import pytest

from bench.metering import MeteringConfigError, RateCard, default_rate_card


def test_default_card_loads():
    rc = default_rate_card()
    assert rc.machine_usd_per_second["sandbox"] > 0
    assert "claude-sonnet" in rc.llm


def test_machine_time_cost():
    rc = RateCard.from_dict({"machine_usd_per_second": {"sandbox": 0.001}})
    assert rc.machine_time_cost("sandbox", 10) == pytest.approx(0.01)
    assert rc.machine_time_cost("SANDBOX", 5) == pytest.approx(0.005)  # case-insensitive
    assert rc.machine_time_cost("unknown", 100) == 0.0                 # unknown kind -> 0


def test_model_prefix_resolution():
    rc = RateCard.from_dict({"llm_usd_per_mtok": {
        "claude-sonnet": {"input": 3, "output": 15},
        "claude-sonnet-4": {"input": 2, "output": 10},
    }})
    assert rc.resolve_model("claude-sonnet-4-20250101") == "claude-sonnet-4"  # longest prefix
    assert rc.resolve_model("claude-sonnet-5") == "claude-sonnet"
    assert rc.resolve_model("gpt-4o") is None


def test_llm_cost_and_unknown_flagging():
    rc = RateCard.from_dict({"llm_usd_per_mtok": {"claude-sonnet": {"input": 3, "output": 15}}})
    usd, key = rc.llm_cost("claude-sonnet-5", 1_000_000, 1_000_000)
    assert usd == pytest.approx(18.0) and key == "claude-sonnet"
    usd, key = rc.llm_cost("mystery-model", 1000, 1000)
    assert usd == 0.0 and key is None


def test_pair_form_llm_rate():
    rc = RateCard.from_dict({"llm": {"m": [1.0, 2.0]}})
    assert rc.llm_cost("m", 1_000_000, 0)[0] == pytest.approx(1.0)


def test_bad_rate_card_rejected():
    with pytest.raises(MeteringConfigError):
        RateCard.from_dict({"llm": {"m": "cheap"}})


def test_from_file_json(tmp_path):
    p = tmp_path / "rates.json"
    p.write_text('{"machine_usd_per_second": {"browser": 0.002}}')
    assert RateCard.from_file(p).machine_time_cost("browser", 1) == pytest.approx(0.002)
