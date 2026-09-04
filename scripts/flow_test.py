#!/usr/bin/env python3
"""End-to-end flow test — hand-wires modules 1-5 on one goal.

This is a manual harness, not the orchestrator (that's module 7). It walks the
task lifecycle from the README by hand so you can watch the pieces cooperate:

    goal -> CEO.decompose -> per task:
              policy check  ->  budget check  ->  acquire worker slot
              ->  hire worker (real Solari machine)  ->  CEO review
    ...then print the audit trace and the spend report.

Usage
-----
    # wiring test — no LLM tokens spent, needs only SOLARI_API_KEY
    python scripts/flow_test.py --fake

    # real run — needs SOLARI_API_KEY and ANTHROPIC_API_KEY
    python scripts/flow_test.py --goal "Launch a landing page for our fintech tool"

Load your keys first:  set -a && . ./.env && set +a

Flags
-----
    --fake            canned plan + scripted worker (no LLM calls)
    --goal TEXT       the goal to pursue
    --budget USD      per-task budget ceiling (default 2.00)
    --max-workers N   concurrent worker cap (default 4)
    --yes             auto-approve ESCALATE decisions instead of prompting
    --verbose         print every agent step as it happens
    --audit-path P    JSONL audit log path (default: a temp file)
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from bench.agents import CEO, FakeLLM, TaskSpec, Verdict, build_worker, llm_from_env  # noqa: E402
from bench.agents.llm import LLMResponse, ToolCall, Usage  # noqa: E402
from bench.audit import AuditLog  # noqa: E402
from bench.metering import BudgetExceeded, Meter, WorkerPoolFull  # noqa: E402
from bench.policy import Dispatch, PolicyEngine  # noqa: E402
from bench.solari import SolariClient  # noqa: E402

BLUE, GREEN, YELLOW, RED, DIM, RESET = (
    "\033[34m", "\033[32m", "\033[33m", "\033[31m", "\033[2m", "\033[0m"
)


def hr(title: str) -> None:
    print(f"\n{BLUE}{'─' * 4} {title} {'─' * max(4, 72 - len(title))}{RESET}")


# --------------------------------------------------------------------------
# Fake scripts (used with --fake). One CEO script: plan, then review.
# --------------------------------------------------------------------------

def fake_ceo() -> FakeLLM:
    plan = {
        "tasks": [{
            "title": "Build and serve the landing page",
            "capability": "sandbox",
            "instructions": (
                "Write a single-file index.html for the product in the goal, serve it on "
                "port 8000, and return the live preview URL."
            ),
            "success_criteria": ["index.html exists", "server responds on :8000", "a live URL is returned"],
        }],
        "notes": "canned single-task plan for the flow test",
    }
    review = {"verdict": "ACCEPT", "reason": "index.html is served on :8000 and a live URL was returned"}
    return FakeLLM(model="claude-sonnet-5", script=[
        LLMResponse(tool_calls=(ToolCall("c1", "submit_plan", plan),), stop_reason="tool_use", usage=Usage(400, 120)),
        LLMResponse(tool_calls=(ToolCall("c2", "submit_review", review),), stop_reason="tool_use", usage=Usage(300, 40)),
    ])


def fake_worker() -> FakeLLM:
    page = (
        "<!doctype html><meta charset=utf-8><title>Kobo</title>"
        "<h1>Kobo</h1><p>Invoicing built for Nigerian freelancers. Get paid faster.</p>"
    )

    def c(name, args, i):
        return LLMResponse(tool_calls=(ToolCall(f"w{i}", name, args),), stop_reason="tool_use", usage=Usage(600, 90))

    return FakeLLM(model="claude-sonnet-5", script=[
        c("write_file", {"path": "index.html", "content": page}, 1),
        c("run_command", {"cmd": "sh", "args": ["-c", "cd / && nohup python3 -m http.server 8000 >/tmp/s.log 2>&1 & sleep 1; echo up"]}, 2),
        c("preview_port", {"port": 8000}, 3),
        c("finish", {"status": "done", "summary": "Wrote index.html and served it on :8000.",
                     "artifacts": [{"kind": "url", "value": "(from preview_port)", "label": "live site"}]}, 4),
    ])


# --------------------------------------------------------------------------

def dispatch_for(task: TaskSpec) -> Dispatch:
    cap = task.capability.value
    return Dispatch(
        capability=cap,
        action="write" if cap != "sandbox" else None,
        tool=task.tool,
        domain=f"{task.tool}.com" if task.tool else None,
        network="external" if cap == "sandbox" else None,
        task_id=task.id,
        agent="ceo",
        purpose=task.title,
    )


def approve_escalation(task: TaskSpec, reason: str, auto_yes: bool) -> bool:
    print(f"{YELLOW}  ESCALATE{RESET}  {task.title}\n            reason: {reason}")
    if auto_yes:
        print(f"{DIM}            --yes: auto-approved{RESET}")
        return True
    try:
        return input("            approve this task? [y/N] ").strip().lower() in {"y", "yes"}
    except EOFError:
        return False


def main() -> int:
    ap = argparse.ArgumentParser(description="Bench end-to-end flow test")
    ap.add_argument("--goal", default="Launch a landing page for a fintech invoicing tool for Nigerian freelancers")
    ap.add_argument("--fake", action="store_true")
    ap.add_argument("--budget", type=float, default=2.00)
    ap.add_argument("--max-workers", type=int, default=4)
    ap.add_argument("--yes", action="store_true")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--audit-path", default=tempfile.mktemp(prefix="bench-flow-", suffix=".jsonl"))
    args = ap.parse_args()

    if not os.environ.get("SOLARI_API_KEY"):
        print(f"{RED}SOLARI_API_KEY not set. Run:  set -a && . ./.env && set +a{RESET}")
        return 2
    if not args.fake and not os.environ.get("ANTHROPIC_API_KEY"):
        print(f"{RED}ANTHROPIC_API_KEY not set. Use --fake for a wiring test without an LLM.{RESET}")
        return 2

    audit = AuditLog.from_env(backend="jsonl", path=args.audit_path)
    policy = PolicyEngine.from_env()
    meter = Meter(
        task_budget_usd=args.budget, max_workers=args.max_workers,
        on_charge=lambda c: audit.cost_charged(task_id=c.task_id, amount_usd=c.amount_usd,
                                               worker_id=c.worker_id, unit=c.unit, detail=c.detail),
    )
    print(f"{DIM}audit: {args.audit_path}")
    print(f"policy rules: {len(policy.policy_set)}   budget/task: ${args.budget:.2f}   worker cap: {args.max_workers}{RESET}")

    def usage_cb(task_id):
        return lambda model, u: meter.charge_llm(
            task_id=task_id, model=model, input_tokens=u.input_tokens, output_tokens=u.output_tokens)

    def event_cb(prefix):
        def _cb(ev):
            if args.verbose and ev.kind in ("tool_call", "tool_result", "finished", "limit_reached"):
                name = ev.detail.get("name") or ev.detail.get("via") or ""
                tail = f"  {str(ev.detail.get('content', ''))[:80]}" if ev.kind == "tool_result" else ""
                print(f"{DIM}    {prefix} {ev.step:>2}  {ev.kind:<13} {name}{tail}{RESET}")
        return _cb

    ceo_llm = fake_ceo() if args.fake else llm_from_env()
    root_id = "flow-" + os.urandom(3).hex()
    ceo = CEO(ceo_llm, on_event=event_cb("ceo"), on_usage=usage_cb(root_id))

    hr("GOAL")
    print(f"  {args.goal}")
    audit.task_created(task_id=root_id, goal=args.goal, actor="ceo")
    plan = ceo.decompose(args.goal)

    hr(f"PLAN — {len(plan)} task(s)")
    for i, t in enumerate(plan.ordered(), 1):
        print(f"  {i}. [{t.capability.value}] {t.title}" + (f"   after {t.depends_on}" if t.depends_on else ""))
        print(f"     {DIM}{t.instructions}{RESET}")

    outcomes: list[tuple[TaskSpec, str, bool]] = []
    with SolariClient.from_env(launch_timeout_s=120) as solari:
        for task in plan.ordered():
            hr(f"TASK — {task.title}")

            dispatch = dispatch_for(task)
            decision = policy.evaluate(dispatch)
            audit.dispatch_evaluated(task_id=task.id, dispatch=dict(dispatch.__dict__), decision=decision)
            tag = {"ALLOW": GREEN, "DENY": RED, "ESCALATE": YELLOW}.get(decision.effect.value, DIM)
            print(f"  policy   {tag}{decision.effect.value}{RESET}{'  +audit' if decision.audit else ''}  ({decision.reason})")

            if decision.blocked:
                audit.task_state_changed(task_id=task.id, to_state="denied", reason=decision.reason)
                outcomes.append((task, "denied by policy", False))
                continue
            if decision.requires_approval:
                audit.escalation_raised(task_id=task.id, reason=decision.reason, decision=decision)
                ok = approve_escalation(task, decision.reason, args.yes)
                audit.escalation_resolved(task_id=task.id, approved=ok, by="flow-test")
                if not ok:
                    outcomes.append((task, "escalation rejected", False))
                    continue

            try:
                meter.check_budget(task.id, 0.10)
            except BudgetExceeded as e:
                print(f"  {RED}budget   {e}{RESET}")
                outcomes.append((task, "over budget", False))
                continue
            try:
                slot = meter.acquire_worker(task_id=task.id, blocking=False)
            except WorkerPoolFull as e:
                print(f"  {RED}workers  {e}{RESET}")
                outcomes.append((task, "no worker slots", False))
                continue

            worker_id = "w-" + os.urandom(3).hex()
            worker_llm = fake_worker() if args.fake else llm_from_env()
            worker = build_worker(task, worker_llm, solari,
                                  on_event=event_cb(task.capability.value), on_usage=usage_cb(task.id))
            audit.worker_hired(worker_id=worker_id, task_id=task.id, capability=task.capability.value)
            print(f"  hire     {task.capability.value} worker {worker_id}")
            with slot:
                result = worker.run(task)
            audit.worker_dismissed(worker_id=worker_id, task_id=task.id,
                                   outcome=result.status.value, reason=result.error)

            colour = GREEN if result.ok else RED
            print(f"  result   {colour}{result.status.value}{RESET}  steps={result.steps}  "
                  f"tokens={result.usage_input_tokens}/{result.usage_output_tokens}")
            print(f"           {result.summary or result.error}")
            for a in result.artifacts:
                print(f"           {DIM}[{a.kind}] {a.label}: {a.value}{RESET}")
            for t in result.transcript:
                if t.get("name") == "preview_port" and t["kind"] == "tool_result":
                    print(f"           {DIM}preview: {t['content'][:120]}{RESET}")

            try:
                review = ceo.review(task, result)
                state = {"ACCEPT": "done", "REJECT": "rejected", "ESCALATE": "escalated"}[review.verdict.value]
                audit.task_state_changed(task_id=task.id, to_state=state, reason=review.reason)
                rc = {Verdict.ACCEPT: GREEN, Verdict.REJECT: RED, Verdict.ESCALATE: YELLOW}[review.verdict]
                print(f"  review   {rc}{review.verdict.value}{RESET}  {review.reason}")
                outcomes.append((task, f"{review.verdict.value.lower()} — {review.reason}", review.accepted))
            except Exception as e:  # noqa: BLE001
                print(f"  review   {RED}skipped: {e}{RESET}")
                outcomes.append((task, f"{result.status.value} (no review)", result.ok))

    hr("AUDIT TRACE")
    for ev in audit.all():
        print(f"  {DIM}{ev.ts}{RESET}  {ev.kind:<22}  {ev.task_id or ''}  {ev.actor or ''}")
    v = audit.verify()
    print(f"\n  chain verify: {(GREEN if v.ok else RED)}{v}{RESET}")

    hr("SPEND")
    grand = 0.0
    for tid in [root_id] + [t.id for t in plan]:
        rep = meter.report(tid)
        if rep.charge_count:
            grand += rep.total_usd
            print(f"  {tid}  ${rep.total_usd:.4f}   {rep.by_category}")
    print(f"  {DIM}total: ${grand:.4f}{RESET}")

    hr("OUTCOMES")
    for task, outcome, _ in outcomes:
        print(f"  [{task.capability.value}] {task.title}\n      -> {outcome}")

    return 0 if outcomes and all(ok for _, _, ok in outcomes) else 1


if __name__ == "__main__":
    raise SystemExit(main())
