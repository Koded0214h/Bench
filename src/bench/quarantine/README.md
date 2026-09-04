# `bench.quarantine` — "it works", not "a file exists"

Module 6 of Bench. Worker output does not go straight into the company. It comes
here first: rebuilt **from data** in a fresh Solari sandbox, its setup run, its
checks executed. Only output that passes is cleared to merge.

Depends on `bench.solari`. Takes a `WorkerResult` only by duck typing (via
`infer_spec`); the orchestrator wires it.

## Usage

```python
from bench.quarantine import Quarantine, QuarantineSpec, HttpServesCheck
from bench.solari import SolariClient

with SolariClient.from_env() as solari:
    q = Quarantine.from_env(solari)

    result = q.run(QuarantineSpec(
        files={"index.html": html},                       # laid down in a clean box
        setup=[["pip", "install", "-q", "-r", "requirements.txt"]],
        checks=[HttpServesCheck("serves on :8000",
                                ["python3", "-m", "http.server", "8000"],
                                port=8000, body_contains="Kobo")],
    ))

    result.merged        # True -> cleared to merge (passed, or quarantine off)
    result.passed        # every check passed
    result.failure       # the reason string to hand back to the worker
    result.recording_id  # the quarantine sandbox's own recording, for the trail
```

## Why "from data", not a snapshot

The rebuild sandbox is **fresh** — files are written in from their contents, not
restored from a snapshot of the worker's machine. The worker may have browsed
hostile pages or run model-generated code; quarantine is an isolation boundary,
not a continuation of that environment. The orchestrator is responsible for
having the worker export its file contents into the bundle before dismissal.

## Checks

Each check proves one thing works inside the sandbox and never raises out of
`run` — an error becomes `CheckResult(passed=False, ...)`.

| Check | Proves |
|---|---|
| `CommandCheck(name, cmd, args, expect_exit=0, stdout_contains=, stderr_contains=)` | a command runs and exits as expected |
| `PythonCheck(name, code)` | a Python snippet exits 0 |
| `FileCheck(name, path, contains=)` | a file exists (and contains a string) |
| `ParsesCheck(name, path, fmt="json"\|"csv"\|"yaml")` | a data file parses |
| `HttpServesCheck(name, start, port, path="/", expect_status=200, body_contains=, boot_timeout_s=20)` | a server, started in the background, actually answers |

`check_from_dict({"type": "http", ...})` builds one from config;
`QuarantineSpec.from_dict(...)` builds a whole spec.

## `infer_spec(worker_result, files=...)`

Best-effort spec from a result plus a `{path: content}` bundle (also reads
`Artifact(kind="file")` contents from `meta["content"]`):

- `requirements.txt` → a `pip install` setup step; `package.json` → `npm install`
- a `url` artifact + an `.html` file → `HttpServesCheck`
- `.py` → `PythonCheck` (runs it); `.json` / `.yaml` / `.csv` → `ParsesCheck`
- nothing else inferable → a single `FileCheck` so the run still verifies *something*

The orchestrator is expected to refine this.

## Run semantics

1. `BENCH_QUARANTINE=false` → `run` returns `QuarantineResult(passed=True,
   skipped=True)` immediately. (`.merged` is True. Don't do this.)
2. Sandbox launch failure → `passed=False`, `failure` explains. Never raises.
3. Files are written (parent dirs created); each **setup** command runs in order;
   a non-zero exit **short-circuits** — checks don't run, `failure` has the
   command and its stderr.
4. **No checks** → `passed=False`, `"nothing to verify"`. Fails closed.
5. Otherwise every check runs; `passed` is all-of; `failure` concatenates the
   failing checks' details.
6. The sandbox is always destroyed on the way out.

## Config

| Env var | Default | Meaning |
|---|---|---|
| `BENCH_QUARANTINE` | `true` | `false` merges untested |
| `BENCH_QUARANTINE_TEMPLATE` | — | sandbox template for the rebuild env |
| `BENCH_QUARANTINE_TIMEOUT_MS` | `300000` | quarantine sandbox lifetime |

## Tests

```bash
python -m pytest tests/quarantine
```

25 tests, no network: every check type against canned exec results (pass, fail,
stdout/stderr/body matching, timeout), the runner (skip-when-disabled, launch
failure, file materialization incl. nested dirs, all-pass, one-fail reason,
setup short-circuit, no-checks-fails-closed, a check that raises, the event
stream). The real-Solari path (a page that serves, a script that doesn't run) is
covered by a smoke script.
