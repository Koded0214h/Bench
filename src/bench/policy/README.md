# `bench.policy` — the gate before hiring

Module 2 of Bench. No worker is spawned until its **dispatch** passes here. Rules
are declarative YAML, evaluated per dispatch, with four effects.

Depends on nothing but `PyYAML`. Decisions are plain dataclasses — persisting
them is the audit module's job.

## Usage

```python
from bench.policy import PolicyEngine, Dispatch

engine = PolicyEngine.from_env()          # bundled defaults + POLICY_* env

decision = engine.evaluate(Dispatch(
    capability="browser",
    domain="salesforce.com",
    action="write",
    tool="salesforce",
    agent="ops",
    task_id="t_42",
))

decision.effect              # Effect.ESCALATE
decision.allowed             # False
decision.requires_approval   # True
decision.audit               # False
decision.reason              # "Human sign-off required before writing to the CRM."
decision.matched             # (RuleMatch(name="crm-writes-need-approval", ...),)
```

Or let it raise — the orchestrator wants "denied tasks stop here":

```python
from bench.policy import PolicyDenied, PolicyEscalation

try:
    engine.check(dispatch)               # returns the decision, or raises
except PolicyDenied as e:
    ...   # e.decision — rework the task
except PolicyEscalation as e:
    ...   # e.decision — surface to a human
```

## Effects and precedence

| Effect | Meaning |
|---|---|
| `ALLOW` | permit the dispatch |
| `DENY` | block it — no machine is allocated |
| `ESCALATE` | block pending human sign-off |
| `AUDIT` | permit, but flag the dispatch for the audit trail |

Evaluation is **order-independent**. Every enabled rule is tested; then:

```
DENY  beats  ESCALATE  beats  ALLOW  beats  AUDIT  beats  the default effect
```

`AUDIT` resolves to an allow and sets `decision.audit`. An `AUDIT` flag also
sticks when a higher tier wins (e.g. `sandbox-egress` AUDIT + `allow-isolated-
compute` ALLOW → allowed **and** audited). Stealth is just another dispatch
field — it never bypasses a `DENY`.

If no decisive rule matches, `POLICY_DEFAULT_EFFECT` applies: `DENY` (allowlist
posture — recommended) or `AUDIT` (permissive: allow unmatched, but flag it).
Never `ALLOW`.

## Rule format

```yaml
rules:                        # a bare top-level list also works
  - name: crm-writes-need-approval
    match:
      capability: browser
      domain: salesforce.com  # matches salesforce.com and any subdomain
      action: write
    effect: ESCALATE
    reason: "Human sign-off required before writing to the CRM."
    enabled: true             # optional, default true
```

`match` is a mapping of key → expected. **Every** entry must match. An expected
value is a scalar (case-insensitive equality) or a list ("any of"). A key the
dispatch has no value for never matches.

Match keys resolve to a `Dispatch` field first — `capability`, `action`,
`domain`, `url`, `network`, `tool`, `agent`, `task_id`, `stealth`, `purpose` —
then to `Dispatch.metadata`. Special handling:

- **`domain`** — matches the host or any subdomain (`salesforce.com` matches
  `na1.salesforce.com`, not `notsalesforce.com`). A leading `*.` is accepted and
  ignored. `www.` is stripped. If a `Dispatch` has `url` but no `domain`, the
  host is derived from the URL.
- **booleans** (e.g. `stealth`) — compared as booleans.

## Loading

`PolicyEngine.from_env()` / `from_config(PolicyConfig)`:

| Env var | Default | Meaning |
|---|---|---|
| `POLICY_DEFAULT_EFFECT` | `DENY` | effect when nothing matches — `DENY` or `AUDIT` |
| `POLICY_RULES_PATH` | — | extra YAML files/dirs (os path separator), loaded **after** the defaults |
| `POLICY_DISABLE_DEFAULTS` | `false` | skip `default_policy.yaml` bundled with this package |

Directories contribute their `*.yaml` / `*.yml` in sorted order. Duplicate rule
names across the merged set raise `PolicyLoadError`.

`default_policy.yaml` is the set `start.sh` seeds: hard stops (public posting,
anon-upload sites), escalations (CRM writes, payment domains), audited allows
(sandbox egress, CRM reads), and baseline allows (isolated compute, dev-reference
domains). It is a starting point — add ALLOW rules for the domains and tools your
company actually uses.

## Tests

```bash
python -m pytest tests/policy
```

38 tests: matching semantics (subdomains, lists, absent fields, metadata,
booleans), precedence (deny-beats-allow, audit-as-allow, stealth-no-bypass),
default-effect behaviour, YAML loading (both forms, error cases, directory
merge), and the bundled defaults against the README's own examples.
