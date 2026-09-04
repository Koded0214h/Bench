from __future__ import annotations

import dataclasses

import pytest

from bench.audit import AuditLog
from bench.control_plane.api.models import AuditRow, Charge
from bench.control_plane.api.stores import DjangoAuditStore, record_charge
from bench.metering import Meter

pytestmark = pytest.mark.django_db


def test_django_audit_store_chains_and_verifies():
    log = AuditLog(DjangoAuditStore())
    log.task_created(task_id="t1", goal="ship it", actor="ceo")
    log.worker_hired(worker_id="w1", task_id="t1", capability="sandbox")
    log.worker_dismissed(worker_id="w1", task_id="t1", outcome="done")

    assert AuditRow.objects.count() == 3
    assert [r.seq for r in AuditRow.objects.all()] == [0, 1, 2]
    assert log.verify().ok
    # a fresh log over the same table sees the same history
    assert len(AuditLog(DjangoAuditStore())) == 3


def test_django_audit_store_detects_tamper():
    log = AuditLog(DjangoAuditStore())
    log.note("a")
    log.note("b")
    row = AuditRow.objects.get(seq=1)
    row.payload = {"text": "tampered"}
    row.save(update_fields=["payload"])
    result = log.verify()
    assert not result.ok and result.broken_at == 1


def test_record_charge_sink():
    meter = Meter(task_budget_usd=None, on_charge=record_charge)
    meter.charge(task_id="t1", amount_usd=0.25, category="llm")
    meter.charge(task_id="t1", amount_usd=0.10, category="machine_time")
    assert Charge.objects.filter(task_id="t1").count() == 2
    assert sum(c.amount_usd for c in Charge.objects.all()) == pytest.approx(0.35)
