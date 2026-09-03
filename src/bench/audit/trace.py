"""A trace: every audit event for one task, with the views you actually want
when something went wrong — the timeline, the session recordings, the outcome.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterator

from .events import AuditEvent, EventKind


def _parse_ts(ts: str) -> datetime:
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:  # pragma: no cover - defensive
        return datetime.now(timezone.utc)


class Trace:
    def __init__(self, task_id: str, events: list[AuditEvent]) -> None:
        self.task_id = task_id
        self.events = sorted(events, key=lambda e: e.seq)

    def __len__(self) -> int:
        return len(self.events)

    def __iter__(self) -> Iterator[AuditEvent]:
        return iter(self.events)

    def __bool__(self) -> bool:
        return bool(self.events)

    # -- slices ----------------------------------------------------

    def of_kind(self, *kinds: str) -> list[AuditEvent]:
        wanted = set(kinds)
        return [e for e in self.events if e.kind in wanted]

    def kinds(self) -> list[str]:
        seen: list[str] = []
        for e in self.events:
            if e.kind not in seen:
                seen.append(e.kind)
        return seen

    def workers(self) -> list[str]:
        return sorted({e.worker_id for e in self.events if e.worker_id})

    def machines(self) -> list[str]:
        return sorted({e.machine_id for e in self.events if e.machine_id})

    def recordings(self) -> list[dict[str, Any]]:
        """Recording pointers — "watch the exact session", not a summary of it."""

        out = []
        for e in self.of_kind(EventKind.RECORDING_CAPTURED):
            row = dict(e.payload)
            row.setdefault("worker_id", e.worker_id)
            row.setdefault("machine_id", e.machine_id)
            out.append(row)
        return out

    # -- summary --------------------------------------------------

    @property
    def started_at(self) -> datetime | None:
        return _parse_ts(self.events[0].ts) if self.events else None

    @property
    def ended_at(self) -> datetime | None:
        return _parse_ts(self.events[-1].ts) if self.events else None

    def duration_s(self) -> float | None:
        if len(self.events) < 2:
            return None
        return (_parse_ts(self.events[-1].ts) - _parse_ts(self.events[0].ts)).total_seconds()

    def final_state(self) -> str | None:
        changes = self.of_kind(EventKind.TASK_STATE_CHANGED)
        return changes[-1].payload.get("to") if changes else None

    def outcome(self) -> str:
        """A single word for how the task ended, derived from its events."""

        state = self.final_state()
        if state:
            return state
        if self.of_kind(EventKind.ESCALATION_RAISED) and not self.of_kind(EventKind.ESCALATION_RESOLVED):
            return "escalated"
        quarantine = self.of_kind(EventKind.QUARANTINE_RESULT)
        if quarantine:
            return "quarantine-passed" if quarantine[-1].payload.get("passed") else "quarantine-failed"
        deny = [
            e for e in self.of_kind(EventKind.DISPATCH_EVALUATED)
            if str(e.payload.get("effect", "")).upper() == "DENY"
        ]
        if deny:
            return "denied"
        return "in-progress"

    def timeline(self) -> list[tuple[str, str, str]]:
        """``(iso_ts, kind, one-line summary)`` per event."""

        return [(e.ts, e.kind, _summarize(e)) for e in self.events]

    def render(self) -> str:
        lines = [f"trace {self.task_id}  ({len(self.events)} events, outcome={self.outcome()})"]
        for ts, kind, summary in self.timeline():
            lines.append(f"  {ts}  {kind:<22}  {summary}")
        recs = self.recordings()
        if recs:
            lines.append("  recordings:")
            for r in recs:
                lines.append(f"    {r.get('provider','?')}:{r.get('recording_id','?')}  {r.get('replay_url') or ''}")
        return "\n".join(lines)


def _summarize(e: AuditEvent) -> str:
    p = e.payload
    if e.kind == EventKind.TASK_CREATED:
        return str(p.get("goal", ""))[:120]
    if e.kind == EventKind.TASK_STATE_CHANGED:
        return f"{p.get('from')} -> {p.get('to')}" + (f"  ({p['reason']})" if p.get("reason") else "")
    if e.kind == EventKind.DISPATCH_EVALUATED:
        return f"{p.get('effect', '?')}" + ("  +audit" if p.get("audit") else "")
    if e.kind == EventKind.WORKER_HIRED:
        return f"{p.get('capability', '?')}  worker={e.worker_id}"
    if e.kind == EventKind.WORKER_DISMISSED:
        return f"{p.get('outcome', '?')}" + (f"  ({p['reason']})" if p.get("reason") else "")
    if e.kind == EventKind.MACHINE_LAUNCHED:
        return f"{p.get('kind', '?')}  machine={e.machine_id}"
    if e.kind == EventKind.MACHINE_DESTROYED:
        return f"machine={e.machine_id}" + (f"  ({p['reason']})" if p.get("reason") else "")
    if e.kind == EventKind.QUARANTINE_RESULT:
        return "passed" if p.get("passed") else f"failed: {str(p.get('failure', ''))[:100]}"
    if e.kind == EventKind.RECORDING_CAPTURED:
        return f"{p.get('provider', '?')}:{p.get('recording_id', '?')}"
    if e.kind == EventKind.ESCALATION_RAISED:
        return str(p.get("reason", ""))[:120]
    if e.kind == EventKind.ESCALATION_RESOLVED:
        return ("approved" if p.get("approved") else "rejected") + (f" by {p['by']}" if p.get("by") else "")
    if e.kind == EventKind.COST_CHARGED:
        return f"${p.get('amount_usd', 0):.4f} {p.get('unit') or ''}".strip()
    if e.kind == EventKind.NOTE:
        return str(p.get("text", ""))[:120]
    return ""


__all__ = ["Trace"]
