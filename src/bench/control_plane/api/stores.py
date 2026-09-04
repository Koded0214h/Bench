"""Adapters that back modules 3 (audit) and 4 (metering) with the database."""

from __future__ import annotations

import contextlib
import threading
from typing import Iterator

from django.db import transaction

from bench.audit.events import AuditEvent

from .models import AuditRow, Charge

_APPEND_LOCK = threading.RLock()


class DjangoAuditStore:
    """An ``bench.audit.store.AuditStore`` backed by the ``AuditRow`` table."""

    @contextlib.contextmanager
    def exclusive(self) -> Iterator[None]:
        # Process-local lock plus a DB transaction: the log's append does
        # last() then append() inside this block.
        with _APPEND_LOCK, transaction.atomic():
            yield

    def last(self) -> AuditEvent | None:
        row = AuditRow.objects.order_by("-seq").first()
        return _to_event(row) if row else None

    def append(self, event: AuditEvent) -> None:
        AuditRow.objects.create(
            seq=event.seq, event_id=event.id, ts=event.ts, kind=event.kind,
            actor=event.actor, task_id=event.task_id, dispatch_id=event.dispatch_id,
            worker_id=event.worker_id, machine_id=event.machine_id,
            payload=dict(event.payload), prev_hash=event.prev_hash, hash=event.hash,
        )

    def read_all(self) -> list[AuditEvent]:
        return [_to_event(r) for r in AuditRow.objects.order_by("seq")]

    def __len__(self) -> int:
        return AuditRow.objects.count()


def _to_event(row: AuditRow) -> AuditEvent:
    return AuditEvent(
        seq=row.seq, id=row.event_id, ts=row.ts, kind=row.kind, prev_hash=row.prev_hash,
        hash=row.hash, actor=row.actor, task_id=row.task_id, dispatch_id=row.dispatch_id,
        worker_id=row.worker_id, machine_id=row.machine_id, payload=dict(row.payload or {}),
    )


def record_charge(charge) -> None:
    """Use as ``Meter(on_charge=record_charge)``. Accepts a bench.metering Charge."""

    Charge.objects.get_or_create(
        charge_id=charge.id,
        defaults=dict(
            ts=charge.ts, task_id=charge.task_id, category=charge.category,
            amount_usd=charge.amount_usd, worker_id=charge.worker_id,
            machine_id=charge.machine_id, unit=charge.unit, quantity=charge.quantity,
            over_budget=charge.over_budget, detail=dict(charge.detail or {}),
        ),
    )
