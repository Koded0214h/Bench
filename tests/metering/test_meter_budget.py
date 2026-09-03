from __future__ import annotations

import pytest

from bench.metering import BudgetExceeded, Meter, RateCard

RC = RateCard.from_dict({
    "machine_usd_per_second": {"sandbox": 0.01},
    "llm_usd_per_mtok": {"claude-sonnet": {"input": 3, "output": 15}},
})


def meter(budget=1.0) -> Meter:
    return Meter(rate_card=RC, task_budget_usd=budget, max_workers=4)


def test_charge_records_and_totals():
    m = meter()
    m.charge(task_id="t", amount_usd=0.25)
    m.charge(task_id="t", amount_usd=0.10)
    assert m.total("t") == pytest.approx(0.35)
    assert m.remaining("t") == pytest.approx(0.65)


def test_check_budget_raises_without_recording():
    m = meter(budget=0.50)
    m.charge(task_id="t", amount_usd=0.40)
    with pytest.raises(BudgetExceeded) as ei:
        m.check_budget("t", 0.20)
    assert ei.value.overage_usd == pytest.approx(0.10)
    assert m.total("t") == pytest.approx(0.40)  # nothing added


def test_check_budget_allows_exact_ceiling():
    m = meter(budget=0.50)
    m.charge(task_id="t", amount_usd=0.30)
    m.check_budget("t", 0.20)  # 0.30 + 0.20 == 0.50, fine


def test_charge_over_budget_is_flagged_and_recorded():
    m = meter(budget=0.50)
    c1 = m.charge(task_id="t", amount_usd=0.40)
    c2 = m.charge(task_id="t", amount_usd=0.30)
    assert c1.over_budget is False
    assert c2.over_budget is True
    assert m.total("t") == pytest.approx(0.70)  # money was spent; books stay honest


def test_charge_raise_over_still_records():
    m = meter(budget=0.10)
    with pytest.raises(BudgetExceeded):
        m.charge(task_id="t", amount_usd=0.25, raise_over=True)
    assert m.total("t") == pytest.approx(0.25)


def test_unlimited_budget_never_exceeds():
    m = Meter(rate_card=RC, task_budget_usd=None)
    m.charge(task_id="t", amount_usd=9999)
    assert m.remaining("t") is None
    assert m.would_exceed("t", 1e9) is False
    m.check_budget("t", 1e9)  # no raise


def test_per_task_budget_override():
    m = meter(budget=1.0)
    m.set_task_budget("vip", 100.0)
    m.check_budget("vip", 50.0)
    with pytest.raises(BudgetExceeded):
        m.check_budget("other", 2.0)


def test_charge_machine_time_uses_rate_card():
    m = meter(budget=10)
    c = m.charge_machine_time(task_id="t", machine_id="m1", kind="sandbox", seconds=30)
    assert c.amount_usd == pytest.approx(0.30)
    assert c.unit == "seconds" and c.quantity == pytest.approx(30)


def test_charge_llm_flags_unpriced_model():
    m = meter(budget=10)
    c = m.charge_llm(task_id="t", model="gpt-4o", input_tokens=1000, output_tokens=1000)
    assert c.amount_usd == 0.0
    assert c.detail["priced"] is False


def test_on_charge_sink_called():
    seen = []
    m = Meter(rate_card=RC, task_budget_usd=None, on_charge=seen.append)
    m.charge(task_id="t", amount_usd=1.0)
    assert len(seen) == 1 and seen[0].task_id == "t"


def test_machine_session_charges_on_exit():
    ticks = iter([100.0, 105.0])  # session start, session end (+5s)
    m = Meter(rate_card=RC, task_budget_usd=None, clock=lambda: next(ticks))
    with m.machine_session(task_id="t", machine_id="m1", kind="sandbox") as info:
        assert "seconds" not in info
    assert info["seconds"] == pytest.approx(5.0)
    assert m.total("t") == pytest.approx(0.05)
    assert m.report("t").by_category["machine_time"] == pytest.approx(0.05)
