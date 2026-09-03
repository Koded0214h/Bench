# `bench.solari` — compute layer client

Module 1 of Bench. A **synchronous facade over the official Solari SDKs**
(`solari-sandbox`, `solari-desktop`, `solari-browser`). Everything else in Bench
touches Solari only through `SolariClient`.

The SDKs are async (`solari-browser` is async-only — it speaks the Playwright
wire protocol). Bench's orchestration is synchronous, so this package runs one
asyncio loop on a daemon thread (`_loop.LoopThread`) and drives all three SDKs on
it. Callers see plain blocking methods.

## Usage

```python
from bench.solari import SolariClient

with SolariClient.from_env() as solari:            # reads SOLARI_* env vars

    # Run model-generated code in a throwaway micro-VM.
    with solari.launch_sandbox(timeout_ms=600_000) as box:
        box.exec("pip", args=["install", "-r", "requirements.txt"])
        box.exec("python", args=["app.py"], background=True)
        url = box.preview_url(8000)                # public preview URL
        snap = box.snapshot(name="pre-merge")     # for quarantine / replay
    # box.kill() runs here, VM destroyed

    # Drive a real web UI with a login captured earlier by a human.
    with solari.launch_browser(profile="salesforce", stealth=True) as br:
        cdp = br.cdp_endpoint                      # hand to the automation layer
    # session released here

    # A screen for computer-use agents.
    with solari.launch_desktop(resolution="1280x720") as d:
        d.open("mousepad")
        d.click(320, 300); d.type_text("hi")
        png = d.screenshot()
    # d.close() + client.destroy() run here
```

`launch_*` creates the machine, waits for it to be usable (sandbox: control
channel connected; desktop: `health().ready`; browser: session issued), and
returns a handle. Every handle is a context manager whose `__exit__` runs the
correct terminal call — `kill()` for a sandbox, `close()` + `destroy()` for a
desktop, `release()` for a browser session — so a returning **or raising** worker
never leaks a VM or a browser slot. Teardown is best-effort and never raises.

Not usable within the launch window → `MachineLaunchError`.

## Surface

| Capability | `launch_*` | Handle | Key methods |
|---|---|---|---|
| Sandbox | `launch_sandbox(template, timeout_ms, cpu, mem_mb, envs, from_snapshot, …)` | `SandboxHandle` | `exec(cmd, args=[…])` · `run_code` · `create_code_context` · `read_text`/`write_text` · `preview_url(port)` · `snapshot(name)` · `set_timeout` · `.raw` |
| Browser | `launch_browser(profile / profile_id, recording, stealth, captcha, proxy)` | `BrowserHandle` | `.ws_endpoint` · `.cdp_endpoint` · `get_replay_url` · `download_replay` · `release_and_wait` · `.raw` |
| Desktop | `launch_desktop(template, resolution, timeout_ms, record, …)` | `DesktopHandle` | `.stream_url` · `health` · `open` · `click` · `type_text` · `press` · `screenshot` · `exec` · `.raw` |

Browser login reuse: `client.list_profiles()` / `create_profile(name)` /
`delete_profile(id)`. `launch_browser(profile="name")` resolves the name to an id.

`.raw` on any handle is the underlying SDK object (`solari_core.Sandbox` /
`solari_core.Desktop` / `solari_browser.Session`) for calls not wrapped here —
run its coroutines via `handle._loop.run(...)` if needed.

## Config (`SolariConfig.from_env`)

| Env var | Default | Meaning |
|---|---|---|
| `SOLARI_API_KEY` | — (required) | `slr_live_…`, from `console.getsolari.com` |
| `SOLARI_BASE_URL` | `https://api.getsolari.com` | gateway; non-default also overrides browser region routing |
| `SOLARI_REGION` | `us-west` | browser SDK region |
| `SOLARI_CALL_TIMEOUT_MS` | `30000` | per-RPC timeout for sandbox/desktop control channels |
| `SOLARI_LAUNCH_TIMEOUT_S` | `120` | how long `launch_*` waits for readiness |

`default_machine_timeout_ms` (15 min) is the rolling idle window applied when a
caller doesn't pass `timeout_ms`. **It resets on every use** — it is not a hard
deadline.

## Errors

`bench.solari` raises `SolariConfigError` and `MachineLaunchError` (both under
`BenchSolariError`). SDK calls raise the SDKs' own exceptions, re-exported here:
`VMSolariError` / `VMTimeoutError` (sandbox + desktop, from `solari_core`),
`BrowserSolariError` (from `solari_browser`), plus `GatewayError`, `AuthError`,
`PlanError`, `ConcurrencyLimitError`, `NoCapacityError`, `ActionError`.
`ANY_SOLARI_ERROR` is a tuple of all three roots for a broad `except`.

## Tests

```bash
python -m pytest tests/solari
```

No network. `SolariBackends` is the factory seam — `conftest.py` passes fake
async SDK clients so the facade (loop bridging, kwarg mapping, readiness waits,
guaranteed teardown, profile resolution) is exercised end to end without hitting
`api.getsolari.com`.

## Not yet wired

- **Login capture** (`manage.py capture_session` in the root README) needs
  Playwright to drive the interactive login and `profiles.save(storageState)`.
  That lands with the CLI module; here you get profile CRUD only.
- Volumes, PTY, and the desktop record/stream sub-APIs are reachable via `.raw`
  but not surfaced as sync methods yet.
