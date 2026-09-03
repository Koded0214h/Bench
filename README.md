# Bench

**A company staffed by AI agents that actually do the work.**

Bench gives every agent a real computer. A browser it can log into your tools with, a Linux sandbox it can run code in, a desktop it can click through. Agents are hired when there is work, do the work end to end, and are dismissed when it is done.

Nothing here is a chat log pretending to be a company.

Built on [Solari](https://solari.com) for agent compute, governed by AOS for policy and audit.

---

## Why this exists

Most "AI company" projects are agents sending each other text. A CEO agent writes a memo. A PM agent turns it into a spec. An engineer agent writes files to disk. Nothing runs. Nothing deploys. Nothing touches a real system. The output is a folder of documents that reads like work.

The second wave — the AI employee startups — fixed the wrong half. They gave agents integrations. Every one of them is really a connector company: the agent is thin, and the value is in the forty APIs they wired up. Which means an agent can only touch the tools someone built a connector for, and every new tool is a roadmap item.

Bench takes the other path.

**An AI employee doesn't need an integration. It needs a browser and a login.**

If a human can do the job in a web UI, the agent can do the job in the same web UI. No API key, no OAuth app, no partner program, no waiting for a connector. Salesforce is the reference integration here, and it works exactly the way it would for a new hire: log in once, and the session persists.

That's the whole thesis. Everything below is the machinery that makes it safe.

---

## What it does

```
You: "We're launching a fintech tool for Nigerian freelancers.
      Get me a landing page live, and log the launch in Salesforce."

CEO agent          → breaks the goal into two tasks, writes the brief
Policy engine      → checks each task before anyone is hired
Engineering agent  → hired, gets a sandbox
                     writes the page, runs it, returns a live URL
Ops agent          → hired, gets a browser with a saved Salesforce login
                     creates the campaign record through the actual UI
Quarantine         → both outputs tested in a clean sandbox before merge
CEO agent          → reports back with the URL and the record ID
Both workers       → dismissed, machines destroyed
```

Every step is traced. Every dispatch is policy-checked. Every machine is disposable.

---

## The org model

Two kinds of agents, and the difference matters.

**Management persists.** The CEO agent and its direct reports are long-lived. They hold the company's goals, memory, budget, and standards. They don't do the work. They decide what work exists, who to hire for it, and whether what came back is acceptable.

**Workers are hired per task.** When a task is created, a worker is spawned with exactly one job, exactly one machine, and exactly the permissions that job requires. It runs to completion or failure, hands back its output, and is dismissed. The machine is destroyed with it.

This is a supervisor pattern with disposable labour, and it exists for three practical reasons:

- **Blast radius.** A compromised or confused worker holds one machine with one set of credentials for one task. Kill it and nothing survives.
- **Cost.** Idle agents holding VMs is the fastest way to a surprise bill. Workers exist only while working.
- **Parallelism.** Twenty workers is twenty machines, all at once. Solari boots them in about a second each, so hiring is cheap enough to do freely.

Management agents never touch a machine. Only workers get hands.

---

## Guardrails

The interesting problem is not making agents act. It's making agents act *as your company* without embarrassing you. Three gates, in order.

### 1. Policy check before hiring

No worker is spawned until the task passes the policy engine. Rules are declarative and evaluated per dispatch, with four effects: `ALLOW`, `DENY`, `AUDIT`, `ESCALATE`.

```yaml
- name: no-public-posting
  match: { capability: browser, domain: [x.com, linkedin.com, reddit.com] }
  effect: DENY
  reason: "Agents may not post publicly under the company identity."

- name: crm-writes-need-approval
  match: { capability: browser, domain: salesforce.com, action: write }
  effect: ESCALATE
  reason: "Human sign-off required before writing to the CRM."

- name: sandbox-egress
  match: { capability: sandbox, network: external }
  effect: AUDIT
```

A denied task never gets a machine. It's logged with the rule that stopped it and surfaced to the CEO agent, which either reworks the task or escalates to you.

Stealth browsing does not exempt an agent from this. Being hard to detect is not permission.

### 2. Quarantine before integration

Agent output does not go straight into the company. It goes into a fresh sandbox first, where it's built, run, and tested. A landing page has to actually serve on a port. A script has to actually execute. A data pull has to actually parse.

Only output that survives quarantine gets merged. Everything else goes back to the worker with the failure attached, or escalates after the retry budget is spent.

This is the gate that separates "the agent produced a file" from "the thing works," and it is the specific failure that killed the previous version of this project.

### 3. Audit trail

Every dispatch, every machine, every policy decision, and every session recording is retained. When something goes wrong you can watch the exact browser session where it went wrong, not read a summary of it.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                        Control Plane                         │
│                                                              │
│   CEO + Management Agents      Policy Engine                 │
│   Company Memory / Goals       Metering + Budget             │
│   Hiring & Dismissal           Audit Log + Traces            │
└───────────────────────────┬──────────────────────────────────┘
                            │  hire(task, capability, limits)
┌───────────────────────────▼──────────────────────────────────┐
│                    Worker Pool (ephemeral)                   │
│                                                              │
│   Engineering        Ops              Research               │
│   → sandbox          → browser        → browser              │
│   runs + serves      real UI, saved   reads real pages       │
│   real code          login, no API    at real scale          │
└───────────────────────────┬──────────────────────────────────┘
                            │
┌───────────────────────────▼──────────────────────────────────┐
│                          Solari                              │
│                                                              │
│   Browser · Sandbox · Desktop                                │
│   Saved sessions · Snapshots · Port preview · Recording      │
└──────────────────────────────────────────────────────────────┘
```

**Control plane** — Django REST API. Agent registry and identity, policy evaluation, LangGraph orchestration, usage metering, immutable audit log.

**Workers** — spawned per task, each bound to one Solari machine and one credential scope.

**Solari** — the compute layer. Machines boot in about a second and are destroyed on dismissal.

---

## Task lifecycle

1. **Goal** arrives from you, or from a management agent's own planning loop.
2. **Decomposition.** CEO agent splits it into tasks with explicit success criteria.
3. **Policy check.** Each task is evaluated. Denied tasks stop here.
4. **Hire.** A worker is spawned with one capability and a machine to match.
5. **Work.** The worker acts. Sessions are recorded. Output is captured as artifacts, not prose.
6. **Quarantine.** Output is rebuilt and tested in a clean sandbox.
7. **Review.** Management accepts, rejects with reason, or escalates to you.
8. **Dismiss.** Worker terminated, machine destroyed, cost attributed to the task.

Failure is a first-class path. A worker gets a bounded retry budget. After that the task escalates rather than looping, which is the failure mode that kills most multi-agent systems.

---

## Quick start

### Prerequisites

- Python 3.11+
- Node.js 18+
- A Solari API key
- An LLM API key (Anthropic or Gemini)

### Setup

```bash
git clone <repo-url> bench
cd bench

cp .env.example .env
# Required:
#   SOLARI_API_KEY=...
#   ANTHROPIC_API_KEY=...

./start.sh
```

`start.sh` runs migrations, seeds the default policy set, provisions JWTs, and runs a smoke test that boots and destroys one sandbox to confirm your Solari key works.

### Save a tool login

Workers reuse browser sessions rather than storing credentials. You log in once, by hand:

```bash
python manage.py capture_session --tool salesforce
```

This opens a live browser you drive yourself. Log in, close it, and the session is saved for workers to reuse. Your password is never held by an agent.

### Run the company

```bash
python -m bench.run "Launch a landing page for our fintech tool and log the campaign in Salesforce"
```

Watch it at `http://localhost:8000/live` — every active worker, its machine, and its live view.

---

## What's real and what isn't

Stated plainly, because a demo that overclaims is worse than a small one that doesn't.

**Real:**
- Workers get genuine Solari machines and genuinely execute
- The landing page actually runs and returns a live, openable URL
- Salesforce is driven through the real web UI with no API key
- Policy denials genuinely block execution before a machine is allocated
- Quarantine genuinely rebuilds and tests output before merge

**Not yet:**
- Deployment means a live sandbox preview URL, not a production host with your domain
- One reference tool is wired end to end. Others work, but haven't been hardened.
- Browser automation against a changing UI is brittle. When Salesforce moves a button, the ops agent needs a nudge.
- Management agents plan well over a handful of tasks and get vague past that
- Two-factor prompts hand control back to you rather than being handled

---

## Configuration

| Variable | Description |
|---|---|
| `SOLARI_API_KEY` | Required. Agent compute. |
| `ANTHROPIC_API_KEY` | Required unless using another provider. |
| `BENCH_MAX_WORKERS` | Concurrent worker cap. Default 10. |
| `BENCH_TASK_BUDGET_USD` | Hard spend ceiling per task. |
| `BENCH_RETRY_LIMIT` | Retries before escalation. Default 2. |
| `BENCH_QUARANTINE` | Set `false` to merge output untested. Don't. |
| `POLICY_DEFAULT_EFFECT` | `DENY` or `AUDIT`. Ships as `DENY`. |

---

## Security

Workers execute untrusted, model-generated code and browse the open web on your behalf. That's the point, and it's also the risk.

- Never give a worker credentials beyond its task scope
- Keep `POLICY_DEFAULT_EFFECT=DENY` — allowlist capabilities, don't blocklist them
- Treat page content as hostile. A page can contain instructions aimed at your agent, and a worker reading it may follow them. Quarantine assumes this.
- Set a budget ceiling before your first parallel run
- Change `SECRET_KEY`, set `DEBUG=False`, and use PostgreSQL before this leaves localhost

---

## Roadmap

- Real deployment targets beyond preview URLs
- A hiring market where management picks among worker configurations by past performance
- Snapshot-based task replay for debugging failed runs
- Desktop workers for tools with no usable web UI
- Cross-company memory so management learns which task shapes fail

---

## License

See [LICENSE](./LICENSE).
