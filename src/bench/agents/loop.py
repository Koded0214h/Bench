"""The agent loop: LLM turn -> tool calls -> tool results -> repeat.

Ends when the model calls a ``terminal`` tool (its arguments become the result),
replies with plain text and no tool calls, or the step budget runs out.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from .llm import LLMClient, Message, ToolCall, Usage
from .tools import ToolRegistry, ToolResult

OnEvent = Callable[["AgentEvent"], None]
OnUsage = Callable[[str, Usage], None]  # (model, usage_delta)


@dataclass(frozen=True)
class AgentEvent:
    kind: str  # llm_response | tool_call | tool_result | finished | limit_reached | error
    step: int
    detail: dict[str, Any] = field(default_factory=dict)


class StopReason:
    TERMINAL_TOOL = "terminal_tool"
    PLAIN_TEXT = "plain_text"
    STEP_LIMIT = "step_limit"
    ERROR = "error"


@dataclass
class AgentRun:
    text: str
    result: dict[str, Any] | None       # args of the terminal tool, if one ended the loop
    stopped: str
    steps: int
    usage: Usage
    events: list[AgentEvent]
    messages: list[Message]

    @property
    def ok(self) -> bool:
        return self.stopped in (StopReason.TERMINAL_TOOL, StopReason.PLAIN_TEXT)


def run_agent(
    *,
    llm: LLMClient,
    system: str,
    prompt: str,
    tools: ToolRegistry | None = None,
    max_steps: int = 12,
    max_tokens: int = 4096,
    temperature: float = 0.0,
    on_event: OnEvent | None = None,
    on_usage: OnUsage | None = None,
    history: list[Message] | None = None,
) -> AgentRun:
    registry = tools or ToolRegistry()
    messages: list[Message] = list(history or [])
    messages.append(Message(role="user", content=prompt))
    total = Usage()
    events: list[AgentEvent] = []

    def emit(ev: AgentEvent) -> None:
        events.append(ev)
        if on_event:
            on_event(ev)

    specs = registry.specs()
    for step in range(1, max_steps + 1):
        response = llm.complete(
            messages=messages,
            system=system,
            tools=specs or None,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        total = total + response.usage
        if on_usage:
            on_usage(getattr(llm, "model", "?"), response.usage)
        emit(AgentEvent("llm_response", step, {
            "text": response.text, "tool_calls": [tc.name for tc in response.tool_calls],
            "stop_reason": response.stop_reason,
        }))

        if not response.tool_calls:
            messages.append(Message(role="assistant", content=response.text))
            emit(AgentEvent("finished", step, {"via": "text"}))
            return AgentRun(response.text, None, StopReason.PLAIN_TEXT, step, total, events, messages)

        messages.append(Message(role="assistant", content=response.text, tool_calls=list(response.tool_calls)))

        terminal_result: dict[str, Any] | None = None
        for call in response.tool_calls:
            tool = registry.get(call.name)
            emit(AgentEvent("tool_call", step, {"name": call.name, "arguments": call.arguments}))
            if tool is not None and tool.terminal:
                result = ToolResult(ok=True, content="ok")
                terminal_result = call.arguments
            else:
                result = registry.invoke(call.name, call.arguments)
            messages.append(Message(
                role="tool", tool_call_id=call.id, content=result.content, is_error=not result.ok,
            ))
            emit(AgentEvent("tool_result", step, {
                "name": call.name, "ok": result.ok, "content": _clip(result.content),
            }))

        if terminal_result is not None:
            emit(AgentEvent("finished", step, {"via": "terminal_tool"}))
            return AgentRun(response.text, terminal_result, StopReason.TERMINAL_TOOL, step, total, events, messages)

    emit(AgentEvent("limit_reached", max_steps, {"max_steps": max_steps}))
    return AgentRun("", None, StopReason.STEP_LIMIT, max_steps, total, events, messages)


def _clip(text: str, n: int = 500) -> str:
    return text if len(text) <= n else text[:n] + f"… (+{len(text) - n} chars)"


__all__ = ["run_agent", "AgentRun", "AgentEvent", "StopReason", "OnEvent", "OnUsage"]
