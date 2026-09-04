"""The CEO agent — persistent management.

It does not touch a machine. It decides what work exists (:meth:`decompose`) and
whether what came back is acceptable (:meth:`review`).
"""

from __future__ import annotations

from typing import Any

from .llm import LLMClient
from .loop import OnEvent, OnUsage, run_agent
from .models import Capability, Plan, Review, TaskSpec, Verdict, WorkerResult
from .tools import Tool, ToolRegistry, obj_schema

_DECOMPOSE_SYSTEM = """\
You are the CEO of a company staffed by AI workers. You do not do the work
yourself. You split a goal into the smallest set of independent tasks that,
completed, satisfy it — then hand each to a worker.

Each task gets exactly one capability:
- sandbox : running code — build a script/site, run it, return a live URL or files
- browser : driving a web UI a human would use (a CRM, a dashboard); set `tool`
            to the login name when one is needed (e.g. "salesforce")
- desktop : a GUI that has no usable web UI

Rules:
- Prefer fewer tasks. Two good tasks beat five vague ones.
- Every task needs concrete, checkable success_criteria.
- Use depends_on only for real ordering constraints (reference task titles).
- instructions must be specific enough that a worker who cannot see the goal can
  still do the task.

Call submit_plan exactly once with the full task list."""

_REVIEW_SYSTEM = """\
You are the CEO reviewing a worker's output against the task it was given.

- ACCEPT if the success criteria are met and the artifacts back that up.
- REJECT if they are not met or the output is prose instead of a working
  artifact. Give a specific reason the worker can act on.
- ESCALATE only if the task cannot be completed as written and needs a human
  decision.

Call submit_review exactly once."""

_TASK_ITEM_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "capability": {"type": "string", "enum": [c.value for c in Capability]},
        "instructions": {"type": "string"},
        "success_criteria": {"type": "array", "items": {"type": "string"}},
        "depends_on": {"type": "array", "items": {"type": "string"},
                       "description": "titles of tasks that must finish first"},
        "tool": {"type": ["string", "null"], "description": "saved browser login name, if needed"},
    },
    "required": ["title", "capability", "instructions", "success_criteria"],
    "additionalProperties": False,
}


def _noop(**_kwargs: Any) -> str:
    return "recorded"


class CEO:
    def __init__(
        self,
        llm: LLMClient,
        *,
        company_context: str = "",
        max_steps: int = 4,
        on_event: OnEvent | None = None,
        on_usage: OnUsage | None = None,
    ) -> None:
        self.llm = llm
        self.company_context = company_context.strip()
        self.max_steps = max_steps
        self._on_event = on_event
        self._on_usage = on_usage

    # -- decomposition ------------------------------------------------

    def decompose(self, goal: str, *, max_tasks: int = 6) -> Plan:
        tools = ToolRegistry([Tool(
            name="submit_plan",
            description="Submit the full decomposition of the goal into tasks.",
            parameters=obj_schema(
                {
                    "tasks": {"type": "array", "items": _TASK_ITEM_SCHEMA,
                              "maxItems": max_tasks, "minItems": 1},
                    "notes": {"type": "string", "description": "anything the reviewer should know"},
                },
                required=["tasks"],
            ),
            fn=_noop,
            terminal=True,
        )])

        prompt = goal if not self.company_context else (
            f"Company context:\n{self.company_context}\n\nGoal:\n{goal}"
        )
        run = run_agent(
            llm=self.llm, system=_DECOMPOSE_SYSTEM, prompt=prompt, tools=tools,
            max_steps=self.max_steps, on_event=self._on_event, on_usage=self._on_usage,
        )
        if not run.result:
            raise ValueError(f"CEO did not submit a plan (stopped: {run.stopped}): {run.text[:200]}")

        title_to_id: dict[str, str] = {}
        specs: list[TaskSpec] = []
        for item in run.result.get("tasks", []):
            spec = TaskSpec.from_dict(item)
            title_to_id[spec.title] = spec.id
            specs.append(spec)
        for spec in specs:  # depends_on arrives as titles; resolve to ids where possible
            spec.depends_on = [title_to_id.get(d, d) for d in spec.depends_on]
        return Plan(goal=goal, tasks=specs, notes=run.result.get("notes", ""))

    # -- review -------------------------------------------------------

    def review(self, task: TaskSpec, result: WorkerResult) -> Review:
        tools = ToolRegistry([Tool(
            name="submit_review",
            description="Submit the accept/reject/escalate decision for this task.",
            parameters=obj_schema({
                "verdict": {"type": "string", "enum": [v.value for v in Verdict]},
                "reason": {"type": "string"},
                "notes": {"type": "string"},
            }, required=["verdict", "reason"]),
            fn=_noop,
            terminal=True,
        )])

        artifacts = "\n".join(f"  - [{a.kind}] {a.label or ''} {a.value}" for a in result.artifacts) or "  (none)"
        prompt = (
            f"TASK: {task.title}\n"
            f"Instructions: {task.instructions}\n"
            f"Success criteria:\n" + "\n".join(f"  - {c}" for c in task.success_criteria) + "\n\n"
            f"WORKER RESULT ({result.status.value}):\n"
            f"Summary: {result.summary}\n"
            f"Artifacts:\n{artifacts}"
            + (f"\nError: {result.error}" if result.error else "")
        )
        run = run_agent(
            llm=self.llm, system=_REVIEW_SYSTEM, prompt=prompt, tools=tools,
            max_steps=self.max_steps, on_event=self._on_event, on_usage=self._on_usage,
        )
        if not run.result:
            raise ValueError(f"CEO did not submit a review (stopped: {run.stopped}): {run.text[:200]}")
        return Review(
            verdict=Verdict(run.result["verdict"]),
            reason=run.result.get("reason", ""),
            notes=run.result.get("notes", ""),
        )


__all__ = ["CEO"]
