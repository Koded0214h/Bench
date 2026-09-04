"""Tools an agent can call, and a registry to hold them.

A :class:`Tool` wraps a plain Python callable with a name, a description, and a
JSON Schema for its arguments. Invocation coerces the return value to a
:class:`ToolResult` and never raises out of the tool — a failing tool comes back
as ``ToolResult(ok=False, ...)`` so the agent can read the error and adjust.
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from typing import Any, Callable

from .llm import ToolSpec, tool_result_text


@dataclass
class ToolResult:
    ok: bool
    content: str
    data: dict[str, Any] | None = None

    @classmethod
    def coerce(cls, value: Any) -> "ToolResult":
        if isinstance(value, ToolResult):
            return value
        if isinstance(value, dict):
            return cls(ok=True, content=tool_result_text(value), data=value)
        return cls(ok=True, content=tool_result_text(value))


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict[str, Any]
    fn: Callable[..., Any]
    #: when True, calling this tool ends the agent loop and its args become the result
    terminal: bool = False

    def spec(self) -> ToolSpec:
        return ToolSpec(self.name, self.description, self.parameters)

    def invoke(self, arguments: dict[str, Any]) -> ToolResult:
        try:
            bound = _filter_kwargs(self.fn, arguments)
            return ToolResult.coerce(self.fn(**bound))
        except Exception as exc:  # noqa: BLE001 - surfaced to the model, not raised
            return ToolResult(ok=False, content=f"{type(exc).__name__}: {exc}")


def _filter_kwargs(fn: Callable[..., Any], arguments: dict[str, Any]) -> dict[str, Any]:
    try:
        sig = inspect.signature(fn)
    except (TypeError, ValueError):  # pragma: no cover
        return dict(arguments)
    if any(p.kind is inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()):
        return dict(arguments)
    return {k: v for k, v in arguments.items() if k in sig.parameters}


class ToolRegistry:
    def __init__(self, tools: list[Tool] | None = None) -> None:
        self._tools: dict[str, Tool] = {}
        for t in tools or []:
            self.add(t)

    def add(self, tool: Tool) -> Tool:
        if tool.name in self._tools:
            raise ValueError(f"duplicate tool: {tool.name}")
        self._tools[tool.name] = tool
        return tool

    def tool(
        self,
        *,
        name: str | None = None,
        description: str,
        parameters: dict[str, Any] | None = None,
        terminal: bool = False,
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        def deco(fn: Callable[..., Any]) -> Callable[..., Any]:
            self.add(Tool(
                name=name or fn.__name__,
                description=description or (fn.__doc__ or "").strip(),
                parameters=parameters or _NO_ARGS,
                fn=fn,
                terminal=terminal,
            ))
            return fn

        return deco

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def specs(self) -> list[ToolSpec]:
        return [t.spec() for t in self._tools.values()]

    def names(self) -> list[str]:
        return list(self._tools)

    def invoke(self, name: str, arguments: dict[str, Any]) -> ToolResult:
        tool = self._tools.get(name)
        if tool is None:
            return ToolResult(ok=False, content=f"no such tool: {name!r}. Available: {', '.join(self._tools)}")
        return tool.invoke(arguments)

    def __len__(self) -> int:
        return len(self._tools)

    def __contains__(self, name: object) -> bool:
        return name in self._tools


_NO_ARGS: dict[str, Any] = {"type": "object", "properties": {}, "additionalProperties": False}


def obj_schema(properties: dict[str, Any], *, required: list[str] | None = None) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": required or list(properties),
        "additionalProperties": False,
    }


__all__ = ["Tool", "ToolResult", "ToolRegistry", "obj_schema"]
