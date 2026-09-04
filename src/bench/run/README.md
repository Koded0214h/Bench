# `bench.run` / `bench.cli` — module 9

The command line: run the company on a goal, and capture a tool login once.

## `python -m bench.run "<goal>"`

Creates a `Goal` in the control-plane database and runs it through the
orchestrator **in the foreground**, streaming the task lifecycle to your
terminal. The run is persisted, so it also shows up at
`http://localhost:8000/live` while a server is up.

```bash
# needs src/ importable — install the package or set PYTHONPATH
pip install -e .            # then: python -m bench.run "…"  or  bench-run "…"

set -a && . ./.env && set +a

python -m bench.run "Launch a landing page for our fintech tool and log the campaign in Salesforce"
python -m bench.run --fake "Build a landing page"          # canned agents, no LLM spend (real Solari)
python -m bench.run --budget 5 --retries 1 --max-workers 8 "…"
python -m bench.run --quiet "…"                            # just the final summary
```

| Flag | Effect |
|---|---|
| `--fake` | `BENCH_FAKE_LLM=true` — canned plan / build / review, no LLM calls |
| `--budget USD` | `BENCH_TASK_BUDGET_USD` |
| `--max-workers N` | `BENCH_MAX_WORKERS` |
| `--retries N` | `BENCH_RETRY_LIMIT` |
| `--quiet` | skip the per-step stream |

Exit code: `0` if the goal finished `done`, `1` if `blocked`/`failed`, `2` for a
missing key, `130` on Ctrl-C (the goal is left in its current DB state).

It migrates and seeds the default policy set on first run. A goal that ends
`blocked` prints the pending escalations and the `POST /api/escalations/<id>/resolve`
call to approve them.

## `python manage.py capture_session --tool <name>`

Save a browser login once, by hand, as a Solari **profile** named after the tool.
Workers reuse it with `launch_browser(profile="<tool>")` — the password is never
held by an agent.

```bash
python manage.py capture_session --tool salesforce
python manage.py capture_session --tool acme --url https://acme.example/login
```

It creates the profile, opens a cloud browser, and prints a `chrome://inspect`
DevTools endpoint you point your local Chrome at to drive the session. Log in
(2FA included), press Enter, and it saves the session's cookies + localStorage
onto the profile. Known login URLs are built in for salesforce, hubspot, notion,
linear, gmail, github; use `--url` for anything else.

## `bench.cli`

Shared helpers: `load_dotenv()` (minimal `KEY=VALUE` reader; existing env wins),
`setup_django()`, and `StreamingSink` — wraps another `OrchestrationSink` (the
control plane's `DjangoSink`) and narrates each lifecycle hook to stdout.

## Tests

```bash
python -m pytest tests/cli
```

7 tests: `load_dotenv` (reads, quotes, does not override, missing file is a
no-op), `StreamingSink` forwards every hook to its inner sink and prints, and the
`bench.run` entrypoint (missing `SOLARI_API_KEY` / `ANTHROPIC_API_KEY` exit 2;
`--fake` creates the `Goal` row, sets `BENCH_FAKE_LLM`, runs, exits 0; budget /
retries / max-workers flags land in the environment). The real-Solari path is a
smoke run.
