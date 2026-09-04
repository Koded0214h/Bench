from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from bench.agents.llm import LLMResponse, ToolCall, Usage
from bench.audit import AuditLog, InMemoryAuditStore
from bench.metering import Meter
from bench.policy import Effect, PolicyEngine, PolicySet


# --- LLM script helpers ------------------------------------------------

def plan_call(tasks: list[dict], cid="c_plan") -> LLMResponse:
    return LLMResponse(tool_calls=(ToolCall(cid, "submit_plan", {"tasks": tasks}),),
                       stop_reason="tool_use", usage=Usage(300, 90))


def review_call(verdict: str, reason: str = "ok", cid="c_rev") -> LLMResponse:
    return LLMResponse(tool_calls=(ToolCall(cid, "submit_review", {"verdict": verdict, "reason": reason}),),
                       stop_reason="tool_use", usage=Usage(120, 20))


def worker_finish(status="done", summary="built it", url="https://x-8000.preview.getsolari.com",
                  cid="c_fin") -> LLMResponse:
    artifacts = [{"kind": "url", "value": url, "label": "site"}] if status == "done" else []
    return LLMResponse(
        tool_calls=(ToolCall(cid, "finish", {"status": status, "summary": summary, "artifacts": artifacts}),),
        stop_reason="tool_use", usage=Usage(500, 60),
    )


def sandbox_task(title="Build the page", sc=None) -> dict:
    return {"title": title, "capability": "sandbox",
            "instructions": "make index.html and serve it",
            "success_criteria": sc or ["serves on :8000"]}


# --- fake Solari ------------------------------------------------------

class FakeSandboxHandle:
    def __init__(self):
        self.id = f"sbx_{id(self) % 100000}"
        self.kind = SimpleNamespace(value="sandbox")
        self.closed = False
        self.files: dict[str, str] = {}

    def __enter__(self): return self
    def __exit__(self, *e): self.closed = True

    def exec(self, cmd, *, args=None, cwd=None, env=None, timeout_ms=None, background=False):
        return SimpleNamespace(exitCode=0, stdout="ok", stderr="")

    def write_text(self, p, c): self.files[p] = c
    def read_text(self, p): return self.files.get(p, "")
    def preview_url(self, port): return f"https://{self.id}-{port}.preview.getsolari.com"


class FakeSolari:
    def __init__(self):
        self.sandboxes: list[FakeSandboxHandle] = []

    def launch_sandbox(self, **kw):
        h = FakeSandboxHandle()
        self.sandboxes.append(h)
        return h


# --- fake quarantine -----------------------------------------------

class FakeQuarantine:
    def __init__(self, verdicts: list[bool] | None = None):
        # verdicts[i] = whether the i-th run passes; default: always pass
        self._verdicts = list(verdicts or [])
        self.runs = 0

    def run(self, spec) -> Any:
        i = self.runs
        self.runs += 1
        passed = self._verdicts[i] if i < len(self._verdicts) else True
        return SimpleNamespace(
            passed=passed, merged=passed, skipped=False,
            checks=[SimpleNamespace(to_dict=lambda: {"name": "serves", "passed": passed})],
            failure=None if passed else "check 'serves': HTTP 500",
            to_dict=lambda: {"passed": passed, "checks": []},
        )


# --- fixtures -------------------------------------------------------

@pytest.fixture
def audit() -> AuditLog:
    return AuditLog(InMemoryAuditStore())


@pytest.fixture
def meter() -> Meter:
    return Meter(task_budget_usd=None, max_workers=4)


@pytest.fixture
def allow_policy() -> PolicyEngine:
    return PolicyEngine(PolicySet.from_dicts([
        {"name": "allow-all", "match": {"capability": ["sandbox", "browser", "desktop"]}, "effect": "ALLOW"},
    ]))


@pytest.fixture
def solari() -> FakeSolari:
    return FakeSolari()
