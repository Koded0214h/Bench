"""Shared value types for management and worker agents."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Capability(str, Enum):
    SANDBOX = "sandbox"
    BROWSER = "browser"
    DESKTOP = "desktop"


class Verdict(str, Enum):
    ACCEPT = "ACCEPT"
    REJECT = "REJECT"
    ESCALATE = "ESCALATE"


class WorkerStatus(str, Enum):
    DONE = "done"
    FAILED = "failed"


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


@dataclass
class TaskSpec:
    """One unit of work the CEO carved out of a goal."""

    title: str
    capability: Capability
    instructions: str
    success_criteria: list[str] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)
    tool: str | None = None                  # e.g. "salesforce" — a saved browser login
    context: dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: _id("task"))

    def __post_init__(self) -> None:
        self.capability = Capability(self.capability)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id, "title": self.title, "capability": self.capability.value,
            "instructions": self.instructions, "success_criteria": list(self.success_criteria),
            "depends_on": list(self.depends_on), "tool": self.tool, "context": dict(self.context),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TaskSpec":
        return cls(
            title=str(data["title"]),
            capability=Capability(str(data.get("capability", "sandbox")).lower()),
            instructions=str(data.get("instructions", "")),
            success_criteria=list(data.get("success_criteria") or []),
            depends_on=list(data.get("depends_on") or []),
            tool=data.get("tool"),
            context=dict(data.get("context") or {}),
            id=str(data["id"]) if data.get("id") else _id("task"),
        )


@dataclass
class Plan:
    goal: str
    tasks: list[TaskSpec] = field(default_factory=list)
    notes: str = ""

    def __len__(self) -> int:
        return len(self.tasks)

    def __iter__(self):
        return iter(self.tasks)

    def by_id(self, task_id: str) -> TaskSpec | None:
        return next((t for t in self.tasks if t.id == task_id), None)

    def ordered(self) -> list[TaskSpec]:
        """Dependency order (stable topological sort). Cycles fall back to input order."""

        done: set[str] = set()
        out: list[TaskSpec] = []
        remaining = list(self.tasks)
        while remaining:
            progressed = False
            for task in list(remaining):
                if all(dep in done or self.by_id(dep) is None for dep in task.depends_on):
                    out.append(task)
                    done.add(task.id)
                    remaining.remove(task)
                    progressed = True
            if not progressed:
                out.extend(remaining)
                break
        return out

    def to_dict(self) -> dict[str, Any]:
        return {"goal": self.goal, "notes": self.notes, "tasks": [t.to_dict() for t in self.tasks]}


@dataclass
class Review:
    verdict: Verdict
    reason: str
    notes: str = ""

    def __post_init__(self) -> None:
        self.verdict = Verdict(self.verdict)

    @property
    def accepted(self) -> bool:
        return self.verdict is Verdict.ACCEPT

    def to_dict(self) -> dict[str, Any]:
        return {"verdict": self.verdict.value, "reason": self.reason, "notes": self.notes}


@dataclass
class Artifact:
    kind: str          # "url" | "file" | "record" | "text"
    value: str
    label: str = ""
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "value": self.value, "label": self.label, "meta": dict(self.meta)}


@dataclass
class WorkerResult:
    task_id: str
    status: WorkerStatus
    summary: str = ""
    artifacts: list[Artifact] = field(default_factory=list)
    error: str | None = None
    steps: int = 0
    usage_input_tokens: int = 0
    usage_output_tokens: int = 0
    transcript: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.status = WorkerStatus(self.status)

    @property
    def ok(self) -> bool:
        return self.status is WorkerStatus.DONE

    def artifact_urls(self) -> list[str]:
        return [a.value for a in self.artifacts if a.kind == "url"]

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id, "status": self.status.value, "summary": self.summary,
            "artifacts": [a.to_dict() for a in self.artifacts], "error": self.error,
            "steps": self.steps,
            "usage": {"input_tokens": self.usage_input_tokens, "output_tokens": self.usage_output_tokens},
        }


__all__ = [
    "Capability", "Verdict", "WorkerStatus",
    "TaskSpec", "Plan", "Review", "Artifact", "WorkerResult",
]
