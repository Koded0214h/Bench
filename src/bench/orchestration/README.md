# `bench.orchestration` — the LangGraph state machine

Module 7 of Bench. The seam that turns modules 1–6 into a company: it decomposes
a goal and drives each task through its lifecycle, with a bounded retry budget
that **escalates rather than loops**.

## The per-task graph

```
policy_check ──deny/escalate──▶ END
    │ allow
    ▼
  work ──worker failed──▶ retry_gate ──budget left──▶ work
    │ ok                       │ spent
    ▼                          ▼
quarantine ──fail──▶ retry_gate   ESCALATED ▶ END
    │ pass
    ▼
  review ─────────────────────▶ END   (done | rejected | escalated)
```

`work` counts an attempt each time it runs. `retry_gate` sends it back to `work`
while `attempts < retry_limit + 1`, then escalates with the last failure
attached. The prior failure is fed to the next attempt as task context. A denied
or escalated task ends immediately — no machine is allocated past `policy_check`.

## Usage

```python
from bench.orchestration import Orchestrator
from bench.agents import llm_from_env
from bench.solari import SolariClient
from bench.policy import PolicyEngine
from bench.metering import Meter
from bench.audit import AuditLog
from bench.quarantine import Quarantine

with SolariClient.from_env() as solari:
    orch = Orchestrator(
        llm=llm_from_env(), solari=solari,
        policy=PolicyEngine.from_env(), meter=Meter.from_env(),
        audit=AuditLog.from_env(), quarantine=Quarantine.from_env(solari),
        sink=my_sink,                       # optional — extra persistence
    )
    run = orch.run("Launch a landing page and log the launch in Salesforce")

run.status            # "done" | "blocked" (a task denied/escalated) | "failed"
run.outcomes          # [TaskOutcome(status, attempts, worker_result,
                      #              quarantine_result, review, failure, machine_ids), ...]
```

`Orchestrator` owns the wiring: it writes audit events at every step
(`dispatch.evaluated`, `worker.hired`, `machine.launched/destroyed`,
`worker.dismissed`, `quarantine.result`, `task.state_changed`,
`escalation.raised`) and meters LLM usage per task through `on_usage`. Everything
else — policy, metering, audit, quarantine, solari, the LLM — is **injected**, so
the module has no hard dependency on any provider or on the control plane.

## The sink

`OrchestrationSink` is the hook for persistence *beyond* the audit log:
`on_plan`, `on_dispatch`, `on_worker_hired`, `on_machine`, `on_worker_result`,
`on_quarantine`, `on_review`, `on_escalation`, `on_task_status`. `NullSink` is the
default. `bench.control_plane.sink.DjangoSink` implements it against the Task /
Agent / Machine / Dispatch / Escalation tables — that's how the API's `/api/goals`
run.

## Resuming an escalation

`orch.run_task(spec, skip_policy=True)` runs a single task from `work` onward,
bypassing the policy gate — used by the control plane after a human approves the
escalation that stopped it.

## Config

`OrchestrationConfig.from_env()`:

| Env var | Default | Meaning |
|---|---|---|
| `BENCH_RETRY_LIMIT` | `2` | retries per task; attempts = retries + 1, then escalate |
| `BENCH_TASK_BUDGET_ESTIMATE_USD` | `0.10` | pre-flight budget check per attempt |
| `BENCH_WORKER_MAX_STEPS` | `16` | agent-loop step cap per worker |

## Tests

```bash
python -m pytest tests/orchestration
```

11 tests, no network (`FakeLLM` + fake Solari + fake quarantine, real
policy/metering/audit): happy path with the full audit-kind set and a verified
chain; policy DENY stops before hiring; policy ESCALATE pauses; quarantine
fails-then-passes on retry (fresh machine each attempt); retry budget exhausted →
escalate; worker failure → retry → success; review REJECT → failed goal; budget
exceeded → task failed; multi-task dependency order; decompose failure handled;
sink receives every lifecycle hook. The real-Solari path is a smoke run.
