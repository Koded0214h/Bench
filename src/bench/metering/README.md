# `bench.metering` — spend, budgets, and the worker cap

Module 4 of Bench. Two safety valves for the orchestrator, plus per-task cost
attribution.

Depends on `PyYAML` only (for rate-card files). Emits to `bench.audit` through an
optional `on_charge` callback — no import.

## Usage

```python
from bench.metering import Meter

meter = Meter.from_env()          # BENCH_TASK_BUDGET_USD, BENCH_MAX_WORKERS, BENCH_RATE_CARD_PATH

# Gate 1 — budget. Check before committing to spend.
meter.check_budget("t_1", estimated_usd)        # raises BudgetExceeded

# Gate 2 — concurrency. Blocks at the cap; use blocking=False to fail fast.
with meter.acquire_worker(task_id="t_1", worker_id="w_eng"):
    with meter.machine_session(task_id="t_1", machine_id="sbx_1", kind="sandbox"):
        ...                                      # wall-time charged on exit
    meter.charge_llm(task_id="t_1", model="claude-sonnet-5",
                     input_tokens=120_000, output_tokens=40_000, worker_id="w_eng")

report = meter.report("t_1")
report.total_usd, report.remaining_usd, report.over_budget
report.by_category      # {"machine_time": ..., "llm": ..., "launch": ...}
report.by_worker        # {"w_eng": ...}
```

## Budget

`BENCH_TASK_BUDGET_USD` is the default ceiling for every task; override per task
with `meter.set_task_budget(task_id, usd)`. `None` / unset = unlimited (set one
before your first parallel run).

- **`check_budget(task_id, amount)`** — pure pre-flight gate. Raises
  `BudgetExceeded` if spending `amount` now would cross the ceiling. Records
  nothing.
- **`charge*(...)`** — always records; the money is already spent, so the books
  stay honest. A charge that crosses the ceiling gets `over_budget=True`; pass
  `raise_over=True` to also raise *after* recording.
- `remaining(task_id)`, `would_exceed(task_id, amount)`, `total(task_id)`.

Charge helpers price usage off the rate card: `charge_machine_time(kind,
seconds)`, `charge_launch(kind)`, `charge_llm(model, input_tokens,
output_tokens)`, and raw `charge(amount_usd, category=...)`.
`machine_session(...)` is a context manager that times a block and charges the
machine time (and, by default, the launch fee) on exit.

## Concurrency

`acquire_worker(*, blocking=True, timeout=None)` takes a slot from a
`BoundedSemaphore(BENCH_MAX_WORKERS)`. Blocks until one frees, or raises
`WorkerPoolFull` (`blocking=False`, or the timeout elapses).
`try_acquire_worker(...)` returns `None` instead of raising. The returned
`WorkerSlot` is a context manager and releases exactly once — a double
`release()` is a safe no-op. `active_workers` / `available_slots` are live counts.

## Rate card

`RateCard` turns usage into dollars:

```yaml
machine_usd_per_second: { sandbox: 0.00003, browser: 0.00006, desktop: 0.00010 }
machine_launch_usd:     { sandbox: 0.0, browser: 0.0, desktop: 0.0 }
llm_usd_per_mtok:
  claude-opus:   { input: 15.00, output: 75.00 }
  claude-sonnet: { input: 3.00,  output: 15.00 }
  claude-haiku:  { input: 0.80,  output: 4.00 }
```

Model lookup is exact, then **longest key that prefixes the id** — `claude-sonnet-5`
→ `claude-sonnet`. An unknown model costs `0.0` and the charge carries
`detail.priced = False` so it can be flagged.

`default_rates.yaml` ships **estimates for demo budgeting, not billed prices.**
Point `BENCH_RATE_CARD_PATH` at a file (YAML or JSON) with your real rates, or
build a `RateCard` from your latest invoice.

## Config

| Env var | Default | Meaning |
|---|---|---|
| `BENCH_TASK_BUDGET_USD` | — (unlimited) | hard per-task ceiling |
| `BENCH_MAX_WORKERS` | `10` | concurrent worker cap |
| `BENCH_RATE_CARD_PATH` | — (bundled) | rate card file |

## Tests

```bash
python -m pytest tests/metering
```

31 tests: rate-card math and model-prefix resolution, budget gate vs. recorded
overage, per-task overrides and unlimited mode, `machine_session` timing, the
concurrency cap under a 40-thread stampede, blocking/timeout/non-blocking
acquire, double-release safety, and report breakdowns.
