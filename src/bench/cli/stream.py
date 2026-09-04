"""A sink that prints the task lifecycle to the terminal as it happens.

Wraps another sink (e.g. the control plane's DjangoSink) so persistence still
happens; this one just narrates.
"""

from __future__ import annotations

from typing import Any

B, G, Y, R, D, X = "\033[34m", "\033[32m", "\033[33m", "\033[31m", "\033[2m", "\033[0m"

_COLOUR = {"done": G, "denied": R, "rejected": R, "failed": R, "escalated": Y,
           "running": B, "needs_retry": Y}


class StreamingSink:
    def __init__(self, inner: Any) -> None:
        self._inner = inner

    def _p(self, text: str) -> None:
        print(text, flush=True)

    def on_plan(self, plan) -> None:
        self._inner.on_plan(plan)
        self._p(f"\n{B}▸ plan{X}  {len(plan.tasks)} task(s)")
        for i, t in enumerate(plan.ordered(), 1):
            dep = f"  {D}after {t.depends_on}{X}" if t.depends_on else ""
            self._p(f"  {i}. [{t.capability.value}] {t.title}{dep}")

    def on_dispatch(self, spec, decision) -> None:
        self._inner.on_dispatch(spec, decision)
        c = _COLOUR.get(decision.effect.value.lower(), "")
        self._p(f"\n{B}▸ {spec.title}{X}")
        self._p(f"  policy    {c}{decision.effect.value}{X}"
                f"{'  +audit' if decision.audit else ''}  {D}{decision.reason or ''}{X}")

    def on_escalation(self, spec, reason: str) -> None:
        self._inner.on_escalation(spec, reason)
        self._p(f"  {Y}escalated{X}  {reason}")

    def on_worker_hired(self, spec, worker_id: str) -> None:
        self._inner.on_worker_hired(spec, worker_id)
        self._p(f"  hire      {spec.capability.value} worker {worker_id}")

    def on_machine(self, spec, worker_id: str, handle) -> None:
        self._inner.on_machine(spec, worker_id, handle)
        self._p(f"  machine   {D}{getattr(handle, 'id', '?')[:48]}{X}")

    def on_worker_result(self, spec, worker_id: str, result) -> None:
        self._inner.on_worker_result(spec, worker_id, result)
        c = G if result.ok else R
        self._p(f"  worker    {c}{result.status.value}{X}  {D}steps={result.steps} "
                f"tokens={result.usage_input_tokens}/{result.usage_output_tokens}{X}")
        self._p(f"            {result.summary or result.error}")
        for a in result.artifacts:
            if a.kind != "file":
                self._p(f"            {D}[{a.kind}] {a.label}: {a.value}{X}")

    def on_quarantine(self, spec, result) -> None:
        self._inner.on_quarantine(spec, result)
        if getattr(result, "skipped", False):
            self._p(f"  quarantine {Y}skipped{X}")
            return
        c = G if result.passed else R
        ok = sum(1 for x in result.checks if x.passed)
        self._p(f"  quarantine {c}{'PASS' if result.passed else 'FAIL'}{X}  {ok}/{len(result.checks)} checks"
                + (f"  {D}{result.failure}{X}" if result.failure else ""))

    def on_review(self, spec, review) -> None:
        self._inner.on_review(spec, review)
        c = _COLOUR.get(review.verdict.value.lower(), "")
        c = G if review.verdict.value == "ACCEPT" else (Y if review.verdict.value == "ESCALATE" else R)
        self._p(f"  review    {c}{review.verdict.value}{X}  {review.reason}")

    def on_task_status(self, spec, status: str, *, detail: str = "") -> None:
        self._inner.on_task_status(spec, status, detail=detail)
        if status in ("needs_retry", "running") and detail.startswith("retry"):
            self._p(f"  {Y}{detail}{X}")


__all__ = ["StreamingSink"]
