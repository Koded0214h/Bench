from __future__ import annotations

import pytest

from bench.metering import Meter, MeteringConfig, RateCard

RC = RateCard.from_dict({
    "machine_usd_per_second": {"sandbox": 0.01, "browser": 0.02},
    "llm_usd_per_mtok": {"claude-sonnet": {"input": 3, "output": 15}},
})


def test_report_breaks_down_by_category_and_worker():
    m = Meter(rate_card=RC, task_budget_usd=5.0)
    m.charge_machine_time(task_id="t", machine_id="m1", kind="sandbox", seconds=100, worker_id="eng")
    m.charge_machine_time(task_id="t", machine_id="m2", kind="browser", seconds=50, worker_id="ops")
    m.charge_llm(task_id="t", model="claude-sonnet-5", input_tokens=200_000, output_tokens=100_000, worker_id="eng")

    r = m.report("t")
    assert r.total_usd == pytest.approx(1.0 + 1.0 + (0.6 + 1.5))
    assert r.by_category["machine_time"] == pytest.approx(2.0)
    assert r.by_category["llm"] == pytest.approx(2.1)
    assert r.by_worker["eng"] == pytest.approx(1.0 + 2.1)
    assert r.by_worker["ops"] == pytest.approx(1.0)
    assert r.charge_count == 3
    assert r.budget_usd == 5.0 and r.remaining_usd == pytest.approx(0.9)
    assert r.over_budget is False


def test_report_flags_over_budget():
    m = Meter(rate_card=RC, task_budget_usd=0.5)
    m.charge(task_id="t", amount_usd=0.9)
    r = m.report("t")
    assert r.over_budget is True and r.remaining_usd == pytest.approx(-0.4)


def test_totals_are_task_scoped():
    m = Meter(rate_card=RC, task_budget_usd=None)
    m.charge(task_id="a", amount_usd=1.0)
    m.charge(task_id="b", amount_usd=2.0)
    assert m.total("a") == pytest.approx(1.0)
    assert m.total() == pytest.approx(3.0)
    assert set(m.tasks()) == {"a", "b"}


def test_charge_dict_round_trips():
    m = Meter(rate_card=RC, task_budget_usd=None)
    c = m.charge_machine_time(task_id="t", machine_id="m1", kind="sandbox", seconds=10)
    d = c.to_dict()
    assert d["category"] == "machine_time" and d["detail"]["kind"] == "sandbox"


def test_from_config_reads_env(monkeypatch):
    monkeypatch.setenv("BENCH_TASK_BUDGET_USD", "2.50")
    monkeypatch.setenv("BENCH_MAX_WORKERS", "3")
    m = Meter.from_env()
    assert m.default_task_budget_usd == 2.5
    assert m.max_workers == 3


def test_from_config_custom_rate_card(tmp_path):
    p = tmp_path / "rc.yaml"
    p.write_text("machine_usd_per_second: { sandbox: 1.0 }")
    m = Meter.from_config(MeteringConfig(rate_card_path=str(p)))
    assert m.charge_machine_time(task_id="t", machine_id="m", kind="sandbox", seconds=2).amount_usd == pytest.approx(2.0)
