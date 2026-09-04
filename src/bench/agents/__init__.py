"""Bench agents — module 5.

Management that persists and workers that are hired per task.

* :class:`CEO` — decomposes a goal into :class:`TaskSpec`s, reviews worker output.
  Never touches a machine.
* :class:`EngineeringWorker` / :class:`OpsWorker` / :class:`ResearchWorker` —
  each gets one Solari machine, one job, a tool set bound to that machine, and is
  torn down when done.

The LLM is provider-agnostic (:class:`AnthropicLLM`, :class:`GeminiLLM`,
:class:`FakeLLM`). Policy, metering and audit are wired in by module 7 — agents
take optional ``on_event`` / ``on_usage`` callbacks, not hard dependencies.

    from bench.agents import CEO, EngineeringWorker, llm_from_env
    from bench.solari import SolariClient

    llm = llm_from_env()
    plan = CEO(llm).decompose("Launch a landing page for our fintech tool")

    with SolariClient.from_env() as solari:
        result = EngineeringWorker(llm, solari).run(plan.tasks[0])
        review = CEO(llm).review(plan.tasks[0], result)
"""

from __future__ import annotations

from .browser_tools import BrowserToolset
from .ceo import CEO
from .config import AgentsConfig
from .llm import (
    AnthropicLLM,
    FakeLLM,
    GeminiLLM,
    OpenAICompatLLM,
    LLMClient,
    LLMError,
    LLMResponse,
    Message,
    ToolCall,
    ToolSpec,
    Usage,
    llm_from_env,
)
from .loop import AgentEvent, AgentRun, StopReason, run_agent
from .models import (
    Artifact,
    Capability,
    Plan,
    Review,
    TaskSpec,
    Verdict,
    WorkerResult,
    WorkerStatus,
)
from .tools import Tool, ToolRegistry, ToolResult, obj_schema
from .workers import EngineeringWorker, OpsWorker, ResearchWorker, Worker, build_worker

__all__ = [
    # llm
    "LLMClient", "LLMResponse", "Message", "ToolSpec", "ToolCall", "Usage", "LLMError",
    "AnthropicLLM", "GeminiLLM", "OpenAICompatLLM", "FakeLLM", "llm_from_env",
    # loop / tools
    "run_agent", "AgentRun", "AgentEvent", "StopReason",
    "Tool", "ToolRegistry", "ToolResult", "obj_schema",
    # agents
    "CEO", "Worker", "EngineeringWorker", "OpsWorker", "ResearchWorker", "build_worker",
    "BrowserToolset", "AgentsConfig",
    # models
    "Capability", "Verdict", "WorkerStatus", "TaskSpec", "Plan", "Review", "Artifact", "WorkerResult",
]
