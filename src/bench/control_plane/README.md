# `bench.control_plane` — the Django service

Module 8 of Bench. A Django + DRF service over modules 1–6: an agent / task /
machine registry, policy decisions, the DB-backed audit trail, spend, a `/live`
view, and a hand-wired goal runner (the placeholder for module 7).

## Run it

```bash
./start.sh                              # migrate, seed policy, mint a JWT, Solari smoke test
python manage.py runserver 0.0.0.0:8000
open http://localhost:8000/live
```

`start.sh` reads `.env`. Set `SECRET_KEY`, `DEBUG=False`, and `DATABASE_URL`
(PostgreSQL) before this leaves localhost — see the top-level README's Security
section.

## API

Auth is `IsAuthenticatedOrReadOnly` with SimpleJWT. Reads are open; writes
(`POST`) need a token: `python manage.py provision_token --print`, then
`POST /api/auth/token` or `Authorization: Bearer <access>`.

| Route | What |
|---|---|
| `POST /api/goals` `{text, run?}` | create a goal; `run` (or `BENCH_AUTORUN`) kicks the runner in a background thread |
| `GET /api/goals` · `/api/goals/{id}` | goal + its task tree |
| `POST /api/goals/{id}/run` | (re)start the runner for a goal |
| `GET /api/tasks?goal=&status=` | tasks |
| `GET /api/agents?active=1` | management + worker agents |
| `GET /api/machines?live=1` | Solari machines (worker + quarantine) |
| `GET /api/dispatches?task=` | policy decisions |
| `GET /api/escalations?pending=1` | escalations |
| `POST /api/escalations/{id}/resolve` `{approved, resolved_by, note}` | approve → resumes the gated task in a thread; reject → task rejected |
| `GET /api/audit?task=&worker=&kind=` · `GET /api/audit/verify` | the hash-chained trail + chain check |
| `GET /api/spend?task=` | per-task cost rollup |
| `GET /api/policy/rules` | the seeded rule set |
| `GET /healthz` | liveness (public) |
| `GET /live` | the stopgap dashboard (polls the API) |

## How a goal runs

`bench.control_plane.runner.run_goal(goal_id)` (background thread) is
`scripts/flow_test.py` persisted to the DB — the same lifecycle module 7 will
drive with LangGraph:

```
goal -> CEO.decompose -> Task rows
per task:  Dispatch row + policy.evaluate + audit
           DENY   -> Task.denied, stop
           ESCALATE -> Escalation(pending), Task.escalated, stop
                       (POST .../resolve approved -> resume_after_escalation)
           else -> budget check -> acquire worker slot
                -> Agent(worker) row -> worker.run (real Solari machine,
                   recorded as a Machine row via on_machine)
                -> quarantine.run(infer_spec(result)) -> Task.quarantine
                -> CEO.review -> Task.done / rejected
```

The DB-backed adapters live in `api/stores.py`: `DjangoAuditStore` implements the
`bench.audit` store protocol against `AuditRow` (append-only, chain intact under
`transaction.atomic()` + a process lock); `record_charge` is the
`Meter(on_charge=…)` sink writing `Charge` rows.

`BENCH_FAKE_LLM=1` swaps in a canned plan / build / review so the whole flow runs
against real Solari with no LLM spend.

## Config

| Env var | Default | |
|---|---|---|
| `SECRET_KEY` | dev placeholder | change for production |
| `DEBUG` | `true` | |
| `DATABASE_URL` | — (sqlite at `.bench/db.sqlite3`) | `postgres://…` for PostgreSQL |
| `BENCH_AUTORUN` | `false` | run goals on create |
| `BENCH_FAKE_LLM` | `false` | canned agents, no LLM calls |
| `ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS` | — | needed when `DEBUG=false` |

Plus every `SOLARI_*`, `POLICY_*`, `BENCH_*`, `ANTHROPIC_API_KEY` from the
earlier modules.

## Tests

```bash
python -m pytest tests/control_plane
```

17 tests (pytest-django, sqlite): `DjangoAuditStore` chaining / persistence /
tamper detection, `record_charge`, every API endpoint (goal create with/without
run, filters, spend aggregation, audit + verify, escalation resolve + conflict,
auth required for writes, `/live` renders), and the runner end-to-end with a fake
Solari + fake LLM across the happy path, the audit chain, and a forced policy
DENY. The real-Solari path is covered by a smoke run.
