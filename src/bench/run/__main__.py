"""Entry point:  python -m bench.run "Launch a landing page …"

Creates a Goal in the control-plane database and runs it through the orchestrator
in the foreground, streaming the task lifecycle to the terminal. The run is
persisted, so it is also visible at http://localhost:8000/live while a server is
up (``python manage.py runserver``).
"""

from __future__ import annotations

import argparse
import os
import sys

from bench.cli import load_dotenv, setup_django

B, G, Y, R, D, X = "\033[34m", "\033[32m", "\033[33m", "\033[31m", "\033[2m", "\033[0m"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m bench.run", description="Run the company on a goal.")
    ap.add_argument("goal", nargs="+", help="the goal, in plain English")
    ap.add_argument("--fake", action="store_true", help="canned agents, no LLM calls (real Solari)")
    ap.add_argument("--budget", type=float, help="per-task USD ceiling (BENCH_TASK_BUDGET_USD)")
    ap.add_argument("--max-workers", type=int, help="concurrent worker cap (BENCH_MAX_WORKERS)")
    ap.add_argument("--retries", type=int, help="retries per task before escalation (BENCH_RETRY_LIMIT)")
    ap.add_argument("--quiet", action="store_true", help="only the final summary")
    args = ap.parse_args(argv)
    goal_text = " ".join(args.goal)

    load_dotenv()
    if args.fake:
        os.environ["BENCH_FAKE_LLM"] = "true"
    if args.budget is not None:
        os.environ["BENCH_TASK_BUDGET_USD"] = str(args.budget)
    if args.max_workers is not None:
        os.environ["BENCH_MAX_WORKERS"] = str(args.max_workers)
    if args.retries is not None:
        os.environ["BENCH_RETRY_LIMIT"] = str(args.retries)

    if not os.environ.get("SOLARI_API_KEY"):
        print(f"{R}SOLARI_API_KEY is not set (add it to .env).{X}")
        return 2
    if not args.fake and not os.environ.get("ANTHROPIC_API_KEY"):
        print(f"{R}ANTHROPIC_API_KEY is not set. Use --fake for a wiring run without an LLM.{X}")
        return 2

    setup_django()

    from django.core.management import call_command

    call_command("migrate", verbosity=0, interactive=False)

    from bench.audit import AuditLog
    from bench.control_plane.api.models import Goal
    from bench.control_plane.api.stores import DjangoAuditStore
    from bench.control_plane.runner import run_goal
    from bench.control_plane.sink import DjangoSink
    from bench.cli.stream import StreamingSink

    # seed policy if the table is empty
    from bench.control_plane.api.models import PolicyRule
    if not PolicyRule.objects.exists():
        call_command("seed_policy", verbosity=0)

    goal = Goal.objects.create(text=goal_text)
    print(f"{B}goal{X}  {goal.id}\n  {goal_text}")
    print(f"{D}  live view: http://localhost:8000/live   (start: python manage.py runserver){X}")

    sink_factory = DjangoSink if args.quiet else (lambda g: StreamingSink(DjangoSink(g)))
    try:
        run_goal(goal.id, sink_factory=sink_factory)
    except KeyboardInterrupt:
        print(f"\n{Y}interrupted — goal {goal.id} left in state {Goal.objects.get(pk=goal.id).status}{X}")
        return 130

    goal.refresh_from_db()
    tasks = list(goal.tasks.all())
    colour = {"done": G, "blocked": Y, "failed": R}.get(goal.status, "")
    print(f"\n{B}▸ result{X}  {colour}{goal.status.upper()}{X}")
    for t in tasks:
        tc = {"done": G}.get(t.status, Y if t.status in ("escalated",) else R)
        line = f"  [{t.capability}] {t.title}: {tc}{t.status}{X}  ({t.attempts} attempt(s))"
        print(line)
        if t.status == "escalated":
            for e in t.escalations.filter(status="pending"):
                print(f"      {Y}needs a human:{X} {e.reason}")
                print(f"      {D}approve: POST /api/escalations/{e.id}/resolve  {{\"approved\": true}}{X}")

    # spend + audit integrity
    from bench.control_plane.api.models import Charge
    total = sum(c.amount_usd for c in Charge.objects.all())
    v = AuditLog(DjangoAuditStore()).verify()
    print(f"\n  spend: ${total:.4f}    audit chain: {(G+'ok') if v.ok else (R+'BROKEN')}{X}")

    return 0 if goal.status == "done" else 1


if __name__ == "__main__":
    sys.exit(main())
