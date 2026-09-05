# BENCH — PRODUCT VIDEO / SAAS DEMO

Create a ~75–90 second cinematic SaaS product video for **Bench**.

## Core premise

Bench lets a person create a company and staff that company with AI agents.

The important distinction is that these are not chatbot agents producing text about work. They are workers that receive real computers — browsers, Linux sandboxes, and desktops — and actually perform tasks.

The video must tell a complete story:

**A founder creates a company → gives it a goal → management plans the work → Bench hires workers → workers receive real machines → they perform real work → policy can stop/escalate actions → outputs are verified → workers are dismissed → the company remains running.**

The viewer should finish thinking:

> **“I just watched a company work.”**

Do not make this feel like an abstract AI explainer, an agent architecture presentation, or a generic futuristic AI commercial.

It should feel like a **real product being used**.

---

# IMPORTANT: SHOW THE ACTUAL PRODUCT

The Bench dashboard/interface must be a major part of the video.

Do NOT simply show beautiful static UI mockups.

The interface should visibly behave like a real application:

* cursor movement
* clicks
* text being entered
* buttons changing state
* workers appearing
* task statuses changing
* machines provisioning
* live task progress
* logs appearing
* browser sessions opening
* approval requests appearing
* quarantine checks completing
* workers being dismissed
* company state updating

The audience should be able to tell:

> **This is a working product, not just a concept.**

Use realistic UI latency and transitions. Do not make everything instant or magically morph between states.

The dashboard can use subtle loading states such as:

`Provisioning...`

`Connecting...`

`Working...`

`Awaiting approval...`

`Verifying...`

`Complete`

This will make the demo feel genuinely operational.

---

# PRODUCT FLOW

The complete demo should follow this exact flow.

## SCENE 01 — EMPTY COMPANY

Start on a clean white screen.

Minimal text:

**You have an idea.**

Pause.

Then:

**But an idea isn't a company.**

Transition into the actual Bench application.

Show the company creation interface.

Example:

```text
CREATE COMPANY

Name
[ Northstar ]

What are you building?

[ Financial tools for Nigerian freelancers ]

                         Create company →
```

The cursor clicks **Create company**.

The company is created.

---

## SCENE 02 — THE COMPANY EXISTS

Show the Bench company view.

The interface should feel clean, premium, and operational.

Example:

```text
NORTHSTAR

Your company is ready.

WORK
No active work

PEOPLE
Management
CEO

WORKERS
0

                    + Start something
```

The important visual idea:

**The company exists, but it is empty.**

The user clicks:

**Start something**

---

# SCENE 03 — THE FOUNDER GIVES THE COMPANY WORK

Show a simple task/goal input.

The user types:

```text
Launch our fintech tool for Nigerian freelancers
and log the launch in Salesforce.
```

Click **Run**.

The dashboard changes state.

A new company activity appears:

```text
NEW GOAL

Launch our fintech tool...

Planning...
```

Do not immediately jump to a finished result.

Let the system visibly begin working.

---

# SCENE 04 — MANAGEMENT PLANS

A management agent appears in the company interface.

For example:

```text
CEO
Management

Planning goal...
```

Then the CEO creates tasks:

```text
GOAL
Launch Northstar

TASKS

01  Build landing page
02  Verify deployment
03  Record launch in Salesforce
```

Show the tasks appearing one by one.

The key message:

**Management decides what work exists.**

It does not perform the work itself.

---

# SCENE 05 — BENCH HIRES A WORKER

The first task becomes active:

```text
BUILD LANDING PAGE
```

Bench shows:

```text
HIRING WORKER

Role
Engineering

Capability
Sandbox

Machine
Provisioning...
```

Show a short realistic loading/provisioning sequence.

Then:

```text
WORKER 001
READY

Machine connected
```

The worker appears inside the company dashboard.

The machine/live view opens.

---

# SCENE 06 — REAL WORK

This is one of the most important shots.

Show the worker actually operating a computer.

The worker receives a Linux/sandbox environment.

Show realistic activity:

* terminal opens
* files are created
* code is written
* commands execute
* build runs
* server starts
* browser opens
* landing page loads

Example terminal activity:

```text
$ npm install

added 214 packages

$ npm run build

✓ compiled successfully

$ npm run dev

Local: http://localhost:8000
```

Then show the generated landing page actually rendering in the browser.

The dashboard simultaneously updates:

```text
WORKER 001

Building landing page...

✓ Files created
✓ Build completed
✓ Server running
```

Then:

```text
TASK COMPLETE

Live preview available
```

The point is to visually prove:

**The agent didn't describe the work. It performed the work.**

---

# SCENE 07 — SECOND WORKER

The Salesforce task becomes active.

Show:

```text
TASK

Record launch in Salesforce

HIRING WORKER
```

Create:

```text
WORKER 002
Operations

Capability
Browser

Machine
Provisioning...
```

Again, show the machine becoming ready.

Then open the worker's browser.

---

# SCENE 08 — REAL BROWSER WORK

The browser should look like a real browser session.

Show the worker navigating through Salesforce.

Do NOT present this as an API integration.

The worker should visibly:

* open Salesforce
* navigate to the appropriate area
* open/create a campaign
* fill fields
* type data
* move through the real interface

Show the saved login/session already available.

The visual message is:

> **If a human can use it in a browser, Bench can give the worker a browser.**

---

# SCENE 09 — POLICY INTERRUPTION

While the worker attempts to save the CRM record, interrupt the flow.

The interface changes.

Show a clear policy gate:

```text
ACTION REQUIRES APPROVAL

Salesforce
CREATE CAMPAIGN

Policy:
CRM writes require approval

                    ESCALATE
```

The worker stops.

The browser remains frozen at the relevant action.

Show:

```text
WORKER 002

Awaiting approval...
```

The founder sees the request.

They click:

**Approve**

The policy gate clears.

The worker continues.

This is a critical moment because it demonstrates that Bench is not simply giving an AI unrestricted access to a company.

---

# SCENE 10 — QUARANTINE

The engineering worker's output should NOT immediately become accepted.

Move the artifact into a clean verification environment.

Show:

```text
QUARANTINE

Rebuilding output...
```

Then checks appear sequentially:

```text
BUILD                 ✓
SERVES ON :8000       ✓
OUTPUT VALID          ✓
```

Then:

```text
VERIFIED

Artifact accepted.
```

This should feel like a security/verification checkpoint.

The message:

> **Agents produce work. Bench verifies it.**

---

# SCENE 11 — WORKERS DISMISSED

Both workers finish.

The dashboard shows:

```text
WORKERS

Worker 001
Engineering
Complete

Worker 002
Operations
Complete
```

Then one by one:

```text
DISMISSING WORKER 001

Machine destroyed.
```

Then:

```text
DISMISSING WORKER 002

Machine destroyed.
```

The worker cards disappear.

But the company remains.

This is the key visual distinction:

**Workers are temporary. The company is persistent.**

---

# SCENE 12 — THE COMPANY IS ALIVE

Pull back to the main Bench company interface.

Now it is populated with completed work:

```text
NORTHSTAR

GOAL
Launch Northstar

STATUS
Complete

WORK

✓ Landing page
✓ Verified deployment
✓ Salesforce campaign

LIVE PREVIEW
northstar.preview

CRM
Campaign created
```

The company is no longer empty.

It has accomplished something.

---

# SCENE 13 — FINAL PAYOFF

Transition back to a clean white field.

Text:

**You don't need employees to start.**

Pause.

Then:

**You need a company that can work.**

The Bench teal mark appears.

The word:

# BENCH

appears with the established letter-stagger animation.

Then:

**Staff your company with AI.**

Supporting line:

**Real computers. Real work. Disposable workers.**

End on the Bench interface / company creation CTA.

---

# VISUAL DIRECTION

Keep the visual language from the existing Bench concept:

* white field as the dominant background
* vibrant teal `#10D9C4`
* darker teal `#02857A` for text and UI accents
* Bricolage Grotesque 800 for display typography
* JetBrains Mono for technical UI, logs, statuses, errors and machine output
* minimal, premium, Apple-style product presentation
* generous whitespace
* subtle shadows
* crisp UI
* restrained motion
* no generic sci-fi holograms
* no glowing AI brains
* no humanoid robots
* no floating chatbot bubbles everywhere

The UI should feel like a serious operating system for a company.

The radial burst mark can remain the primary Bench visual signature and should appear at the transition from the empty-company world into the active-company world, then return for the final end card.

---

# MOTION LANGUAGE

The entire video should feel like one continuous composition rather than disconnected clips.

Use a single continuous timeline / clock.

Camera movement should be subtle:

* slow push-ins
* UI zooms
* smooth pans
* occasional rapid transition when a worker is hired
* controlled zoom into live machine sessions
* pull back when the company becomes populated

Use the teal burst as the major transition device.

The video should build in energy:

**empty → curious → active → tense → verified → powerful → calm**

---

# MOST IMPORTANT STORY BEAT

The video should communicate this progression without needing narration:

```text
IDEA
  ↓
COMPANY
  ↓
GOAL
  ↓
PLAN
  ↓
HIRE
  ↓
MACHINE
  ↓
REAL WORK
  ↓
POLICY
  ↓
VERIFICATION
  ↓
DISMISS
  ↓
COMPANY KEEPS RUNNING
```

This is the actual Bench product story.

---

# NARRATIVE PRINCIPLE

Do not explain Bench first.

**Show Bench doing something.**

Do not say:

"Bench uses ephemeral workers."

Show:

`WORKER 001 → machine → work → complete → machine destroyed`

Do not say:

"Bench has browser automation."

Show:

`worker → browser → Salesforce → clicks → types → saves`

Do not say:

"Bench has policy enforcement."

Show:

`worker → blocked → approval → continues`

Do not say:

"Bench verifies agent output."

Show:

`artifact → quarantine → tests → ✓`

The viewer should infer the architecture from the behavior.

---

# FINAL MESSAGE

The final emotional takeaway should be:

> **You start the company.**
>
> **Bench staffs it.**
>
> **The workers do the work.**
>
> **And when the work is done, they leave.**

The product itself should be visible and functioning throughout the majority of the second half of the video.

The result should feel like a **real SaaS product demo wrapped inside a cinematic product story**, not a concept video pretending to be software.

