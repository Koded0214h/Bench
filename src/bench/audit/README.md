# `bench.audit` — the immutable trail

Module 3 of Bench. Every dispatch, every machine, every policy decision, every
session recording — retained, append-only, and hash-chained so tampering shows.

Depends on nothing (stdlib only). Decision objects from `bench.policy` are
accepted by duck typing, not import.

## Usage

```python
from bench.audit import AuditLog

audit = AuditLog.from_env()                 # jsonl at .bench/audit.jsonl by default

audit.task_created(task_id="t_42", goal="Launch a landing page", actor="ceo")
audit.dispatch_evaluated(task_id="t_42", dispatch=dispatch, decision=decision)
audit.worker_hired(worker_id="w_eng", task_id="t_42", capability="sandbox")
audit.machine_launched(machine_id="sbx_1", kind="sandbox", task_id="t_42", worker_id="w_eng")
audit.recording_captured(task_id="t_42", worker_id="w_eng", machine_id="sbx_1",
                         recording_id="rec_x", replay_url="https://replays.getsolari.com/rec_x")
audit.quarantine_result(task_id="t_42", passed=True, checks=["serves on :8000"])
audit.machine_destroyed(machine_id="sbx_1", task_id="t_42", reason="dismissed")
audit.task_state_changed(task_id="t_42", from_state="review", to_state="done")

print(audit.trace("t_42").render())
assert audit.verify()
```

## Events

Each `AuditEvent` carries a gapless `seq`, a UTC `ts`, a `kind`, optional index
fields (`actor`, `task_id`, `dispatch_id`, `worker_id`, `machine_id`), a `payload`
dict, and the chain fields `prev_hash` / `hash` (sha256 over the canonical
serialization of every other field). The first event links to `GENESIS_HASH`.

`append(kind, **fields)` is the raw call; the convenience recorders build the
right payload for the common kinds:

| Recorder | `kind` |
|---|---|
| `task_created` / `task_state_changed` | `task.created` / `task.state_changed` |
| `dispatch_evaluated` | `dispatch.evaluated` (flattens `decision` — `.to_dict()` if present — and lifts `effect` / `audit`) |
| `worker_hired` / `worker_dismissed` | `worker.hired` / `worker.dismissed` |
| `machine_launched` / `machine_destroyed` | `machine.launched` / `machine.destroyed` |
| `quarantine_result` | `quarantine.result` |
| `recording_captured` | `recording.captured` (provider, recording id, replay url, expiry) |
| `escalation_raised` / `escalation_resolved` | `escalation.*` |
| `cost_charged` | `cost.charged` |
| `note` | `note` |

`payload` values are coerced to JSON-friendly data: objects with `to_dict()`,
dataclasses, mappings, iterables, datetimes, UUIDs; anything else falls back to
`str`.

## Integrity

`AuditLog.verify()` walks the chain and returns `VerifyResult(ok, checked,
broken_at, reason)`. It fails on a `seq` gap (a dropped event), a `prev_hash`
that doesn't link, or an event whose own `hash` no longer recomputes (an edited
event). Appends are serialized by an in-process lock **and** — for the JSONL
store — an `flock` held across "read last event, then append", so the chain and
`seq` survive concurrent workers and processes.

There is no update and no delete. That is the point.

## Storage

`AuditLog.from_env()` reads:

| Env var | Default | Meaning |
|---|---|---|
| `BENCH_AUDIT_BACKEND` | `jsonl` | `jsonl` (append-only file) or `memory` (non-persistent) |
| `BENCH_AUDIT_PATH` | `.bench/audit.jsonl` | log path when `jsonl` |

`JsonlAuditStore` writes one JSON object per line and `fsync`s each append.
`InMemoryAuditStore` is for tests and dry runs. Both satisfy the `AuditStore`
protocol (`exclusive()`, `last()`, `append()`, `read_all()`, `__len__`); the
Django-backed store lands with the control plane (module 8).

## Traces

`audit.trace(task_id)` → a `Trace`: `.events` (seq-ordered, task-scoped),
`.of_kind(...)`, `.workers()`, `.machines()`, `.recordings()` (pointers to the
exact Solari sessions), `.final_state()`, `.outcome()` (one word: `done`,
`escalated`, `quarantine-failed`, `denied`, `in-progress`, …), `.duration_s()`,
`.timeline()`, and `.render()` for the human-readable dump.

## Tests

```bash
python -m pytest tests/audit
```

22 tests: deterministic hashing and tamper detection, JSONL persistence and
one-object-per-line, concurrent-append chain integrity (4 threads × 25 writes),
`verify()` catching edited and dropped events, recorder index fields and filter
queries, and trace scoping / recordings / outcome / render.
