# `bench.agents` — management and workers

Module 5 of Bench. The CEO that decides what work exists, and the workers hired
to do it.

Depends on `bench.solari` (workers need machines) and `anthropic`. Policy,
metering, and audit are **not** imported — agents take optional `on_event` /
`on_usage` callbacks that module 7 wires to them.

## The LLM interface

One provider-agnostic surface: `LLMClient.complete(messages, system, tools, ...)`
→ `LLMResponse(text, tool_calls, usage, stop_reason)`.

| Client | Notes |
|---|---|
| `AnthropicLLM(model="claude-sonnet-5")` | Messages API, tool-calling, token usage. `client=` injectable. |
| `GeminiLLM(model="gemini-2-pro")` | experimental — mirrors the interface, not hardened; needs `google-genai` |
| `FakeLLM(script)` | scripted `LLMResponse`s (or `str` / `(text, [ToolCall])`) for tests |

`llm_from_env(model=None)` infers the provider from the model id
(`claude*` → Anthropic, `gemini*` → Gemini); key from `ANTHROPIC_API_KEY` /
`GEMINI_API_KEY`.

## The agent loop

`run_agent(llm, system, prompt, tools, max_steps=12, on_event, on_usage)` runs
LLM turn → tool calls → tool results → repeat. It ends when the model:

- calls a **terminal** tool — its arguments become `AgentRun.result`
- replies with plain text and no tool calls — the text is `AgentRun.text`
- exhausts `max_steps` — `AgentRun.stopped == StopReason.STEP_LIMIT`

A tool that raises comes back to the model as `ToolResult(ok=False, ...)`, not an
exception. Every step emits `AgentEvent`s; per-call token usage goes to
`on_usage(model, usage)`.

`Tool(name, description, parameters, fn, terminal=False)` wraps a callable with a
JSON Schema. `ToolRegistry` holds them; `registry.tool(name=, description=,
parameters=)` is a decorator. `obj_schema({...}, required=[...])` builds the
schema.

## CEO

```python
from bench.agents import CEO, llm_from_env

ceo = CEO(llm_from_env(), company_context="Fintech for Nigerian freelancers.")
plan = ceo.decompose("Launch a landing page and log the launch in Salesforce")
#   -> Plan(goal, tasks=[TaskSpec(title, capability, instructions,
#                                 success_criteria, depends_on, tool), ...])

review = ceo.review(plan.tasks[0], worker_result)
#   -> Review(verdict=ACCEPT|REJECT|ESCALATE, reason, notes)
```

`decompose` runs the loop with one terminal tool, `submit_plan`; `depends_on`
comes back as task titles and is resolved to ids. `review` uses `submit_review`.
The CEO has **no machine tools** — it plans and judges, nothing else.

## Workers

```python
from bench.agents import EngineeringWorker
from bench.solari import SolariClient

with SolariClient.from_env() as solari:
    result = EngineeringWorker(llm, solari).run(task)   # -> WorkerResult
```

| Worker | Machine | Tools |
|---|---|---|
| `EngineeringWorker` | sandbox | `run_command` (argv, not shell) · `write_file` · `read_file` · `preview_port` |
| `OpsWorker` | browser | `navigate` · `read_page` · `find_links` · `click` · `fill` · `press` · `screenshot` |
| `ResearchWorker` | browser (read-only) | `navigate` · `read_page` · `find_links` · `screenshot` |

Every worker also gets a terminal `finish` tool (`status`, `summary`,
`artifacts`). `Worker.run`:

1. launches the machine (`launch_sandbox` / `launch_browser`; a task's `tool`
   becomes the browser `profile`)
2. builds the machine-bound tool set + `finish`
3. runs the agent loop
4. returns `WorkerResult(status, summary, artifacts, steps, usage, transcript)`
5. **tears the machine down** — on success, on failure, on exception

A launch failure, an unhandled exception, or hitting the step limit all come back
as `WorkerResult(status=failed, error=...)`, never a raise.

`OpsWorker` / `ResearchWorker` drive the browser through `BrowserToolset`
(Playwright via patchright over the Solari wire endpoint). It's deliberately
small — browser automation against a changing UI is brittle. `toolset_factory=`
is injectable for tests.

## Config

`AgentsConfig.from_env()` — `BENCH_LLM_MODEL` (`claude-sonnet-5`),
`BENCH_CEO_MAX_STEPS` (4), `BENCH_WORKER_MAX_STEPS` (16), `BENCH_LLM_MAX_TOKENS`
(4096).

## Tests

```bash
python -m pytest tests/agents
```

31 tests, no network: LLM message mapping and `FakeLLM` scripting, `AnthropicLLM`
parsing against a fake client, tool coercion / error capture / kwarg filtering,
the loop (terminal tool, plain text, step limit, multi-call step, error
feedback, usage), CEO decompose (plan parsing, title→id dependency resolution)
and review, and workers end-to-end against a fake Solari (tool execution,
guaranteed teardown, launch-failure and step-limit paths, `task.tool` → browser
profile, read-only research toolset).

The `EngineeringWorker` ↔ real-Solari path is exercised by the smoke script in
the module-5 notes: scripted `FakeLLM`, real sandbox, real `preview_port` URL,
real teardown.
