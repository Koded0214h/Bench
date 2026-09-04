"""Provider-agnostic LLM interface.

One :class:`LLMClient` protocol, one :class:`LLMResponse` shape, tool-calling,
and token usage. Concrete clients: :class:`AnthropicLLM`, :class:`GeminiLLM`
(experimental), and :class:`FakeLLM` for tests.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Protocol, runtime_checkable


class LLMError(Exception):
    pass


@dataclass(frozen=True)
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    def __add__(self, other: "Usage") -> "Usage":
        return Usage(self.input_tokens + other.input_tokens, self.output_tokens + other.output_tokens)


@dataclass
class Message:
    role: str  # "user" | "assistant" | "tool"
    content: str = ""
    #: For role == "assistant": tool calls the model made.
    tool_calls: list["ToolCall"] = field(default_factory=list)
    #: For role == "tool": which call this result answers.
    tool_call_id: str | None = None
    is_error: bool = False


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema for the arguments object


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class LLMResponse:
    text: str = ""
    tool_calls: tuple[ToolCall, ...] = ()
    usage: Usage = Usage()
    stop_reason: str = "end_turn"  # "end_turn" | "tool_use" | "max_tokens" | ...
    raw: Any = None

    @property
    def wants_tools(self) -> bool:
        return bool(self.tool_calls)


@runtime_checkable
class LLMClient(Protocol):
    model: str

    def complete(
        self,
        *,
        messages: list[Message],
        system: str | None = None,
        tools: Iterable[ToolSpec] | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.0,
    ) -> LLMResponse: ...


# --------------------------------------------------------------------------
# Anthropic
# --------------------------------------------------------------------------

class AnthropicLLM:
    """Anthropic Messages API. ``client`` is injectable for tests."""

    def __init__(self, model: str = "claude-sonnet-5", *, api_key: str | None = None, client: Any = None) -> None:
        self.model = model
        if client is not None:
            self._client = client
        else:
            try:
                import anthropic
            except ImportError as exc:  # pragma: no cover
                raise LLMError("anthropic SDK not installed: pip install anthropic") from exc
            self._client = anthropic.Anthropic(api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"))

        # Some SDK builds dropped `temperature` from messages.create(); route it
        # through extra_body when the parameter isn't accepted directly.
        self._temp_kwarg = True
        try:
            import inspect

            self._temp_kwarg = "temperature" in inspect.signature(self._client.messages.create).parameters
        except (TypeError, ValueError):  # pragma: no cover
            pass

    def complete(
        self, *, messages, system=None, tools=None, max_tokens=4096, temperature=0.0,
    ) -> LLMResponse:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": [_to_anthropic_message(m) for m in messages],
        }
        if self._temp_kwarg:
            kwargs["temperature"] = temperature
        else:
            kwargs["extra_body"] = {"temperature": temperature}
        if system:
            kwargs["system"] = system
        tool_specs = list(tools or [])
        if tool_specs:
            kwargs["tools"] = [
                {"name": t.name, "description": t.description, "input_schema": t.parameters}
                for t in tool_specs
            ]
        try:
            resp = self._client.messages.create(**kwargs)
        except Exception as exc:  # noqa: BLE001 - normalize provider errors
            raise LLMError(f"anthropic call failed: {exc}") from exc

        text_parts: list[str] = []
        calls: list[ToolCall] = []
        for block in resp.content:
            btype = getattr(block, "type", None)
            if btype == "text":
                text_parts.append(block.text)
            elif btype == "tool_use":
                calls.append(ToolCall(id=block.id, name=block.name, arguments=dict(block.input or {})))
        usage = Usage(
            getattr(resp.usage, "input_tokens", 0) or 0,
            getattr(resp.usage, "output_tokens", 0) or 0,
        )
        return LLMResponse(
            text="".join(text_parts).strip(),
            tool_calls=tuple(calls),
            usage=usage,
            stop_reason=getattr(resp, "stop_reason", "end_turn") or "end_turn",
            raw=resp,
        )


def _to_anthropic_message(m: Message) -> dict[str, Any]:
    if m.role == "tool":
        return {
            "role": "user",
            "content": [{
                "type": "tool_result",
                "tool_use_id": m.tool_call_id,
                "content": m.content,
                "is_error": m.is_error,
            }],
        }
    if m.role == "assistant" and m.tool_calls:
        content: list[dict[str, Any]] = []
        if m.content:
            content.append({"type": "text", "text": m.content})
        for tc in m.tool_calls:
            content.append({"type": "tool_use", "id": tc.id, "name": tc.name, "input": tc.arguments})
        return {"role": "assistant", "content": content}
    return {"role": m.role, "content": m.content}


# --------------------------------------------------------------------------
# Gemini (experimental — mirrors the interface, not hardened)
# --------------------------------------------------------------------------

class GeminiLLM:
    def __init__(self, model: str = "gemini-2-pro", *, api_key: str | None = None, client: Any = None) -> None:
        self.model = model
        if client is not None:
            self._client = client
        else:
            try:
                from google import genai
            except ImportError as exc:  # pragma: no cover
                raise LLMError("google-genai not installed: pip install google-genai") from exc
            self._client = genai.Client(api_key=api_key or os.environ.get("GEMINI_API_KEY"))

    def complete(  # pragma: no cover - not exercised in CI
        self, *, messages, system=None, tools=None, max_tokens=4096, temperature=0.0,
    ) -> LLMResponse:
        from google.genai import types as gt

        contents = []
        for m in messages:
            role = "model" if m.role == "assistant" else "user"
            if m.role == "tool":
                contents.append(gt.Content(role="user", parts=[
                    gt.Part.from_function_response(name=m.tool_call_id or "tool", response={"content": m.content})
                ]))
            else:
                contents.append(gt.Content(role=role, parts=[gt.Part.from_text(m.content or "")]))
        config = gt.GenerateContentConfig(
            system_instruction=system or None,
            max_output_tokens=max_tokens,
            temperature=temperature,
            tools=[gt.Tool(function_declarations=[
                gt.FunctionDeclaration(name=t.name, description=t.description, parameters=t.parameters)
                for t in (tools or [])
            ])] if tools else None,
        )
        try:
            resp = self._client.models.generate_content(model=self.model, contents=contents, config=config)
        except Exception as exc:  # noqa: BLE001
            raise LLMError(f"gemini call failed: {exc}") from exc

        calls: list[ToolCall] = []
        text_parts: list[str] = []
        for part in (resp.candidates[0].content.parts if resp.candidates else []):
            if getattr(part, "function_call", None):
                fc = part.function_call
                calls.append(ToolCall(id=fc.name, name=fc.name, arguments=dict(fc.args or {})))
            elif getattr(part, "text", None):
                text_parts.append(part.text)
        um = getattr(resp, "usage_metadata", None)
        usage = Usage(
            getattr(um, "prompt_token_count", 0) or 0,
            getattr(um, "candidates_token_count", 0) or 0,
        )
        return LLMResponse(
            text="".join(text_parts).strip(),
            tool_calls=tuple(calls),
            usage=usage,
            stop_reason="tool_use" if calls else "end_turn",
            raw=resp,
        )


# --------------------------------------------------------------------------
# Fake (tests)
# --------------------------------------------------------------------------

class FakeLLM:
    """Returns scripted responses. ``script`` is a list of :class:`LLMResponse`
    (or ``(text, [ToolCall...])`` / plain ``str``), or a callable
    ``(messages, tools) -> LLMResponse``."""

    def __init__(self, script: list[Any] | Callable[..., LLMResponse], *, model: str = "fake-1") -> None:
        self.model = model
        self._script = script
        self._i = 0
        self.calls: list[dict[str, Any]] = []

    def complete(self, *, messages, system=None, tools=None, max_tokens=4096, temperature=0.0) -> LLMResponse:
        self.calls.append({
            "messages": [Message(role=m.role, content=m.content, tool_calls=list(m.tool_calls),
                                 tool_call_id=m.tool_call_id, is_error=m.is_error) for m in messages],
            "system": system,
            "tools": [t.name for t in (tools or [])],
        })
        if callable(self._script):
            return self._coerce(self._script(messages, tools))
        if self._i >= len(self._script):
            raise LLMError(f"FakeLLM script exhausted after {self._i} calls")
        item = self._script[self._i]
        self._i += 1
        return self._coerce(item)

    @staticmethod
    def _coerce(item: Any) -> LLMResponse:
        if isinstance(item, LLMResponse):
            return item
        if isinstance(item, str):
            return LLMResponse(text=item, usage=Usage(10, 5))
        if isinstance(item, tuple) and len(item) == 2:
            text, calls = item
            calls = tuple(calls)
            return LLMResponse(text=text or "", tool_calls=calls, usage=Usage(10, 5),
                               stop_reason="tool_use" if calls else "end_turn")
        raise LLMError(f"cannot coerce {item!r} to LLMResponse")


# --------------------------------------------------------------------------
# OpenAI-compatible /chat/completions (Groq, OpenRouter, Cerebras, Ollama, …)
# --------------------------------------------------------------------------

class OpenAICompatLLM:
    """Any endpoint that speaks OpenAI's ``/chat/completions`` with tool calling.

    Works with free providers: Groq, OpenRouter (``:free`` models), Cerebras,
    and a local Ollama / LM Studio. Uses raw httpx — no ``openai`` package.
    """

    def __init__(
        self,
        model: str,
        *,
        base_url: str,
        api_key: str | None = None,
        timeout_s: float = 120.0,
        client: Any = None,
    ) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self._api_key = api_key
        if client is not None:
            self._client = client
        else:
            import httpx

            headers = {"Content-Type": "application/json"}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"
            self._client = httpx.Client(base_url=self.base_url, timeout=timeout_s, headers=headers)

    def complete(self, *, messages, system=None, tools=None, max_tokens=4096, temperature=0.0) -> LLMResponse:
        wire: list[dict[str, Any]] = []
        if system:
            wire.append({"role": "system", "content": system})
        for m in messages:
            wire.append(_to_openai_message(m))

        body: dict[str, Any] = {
            "model": self.model,
            "messages": wire,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        tool_specs = list(tools or [])
        if tool_specs:
            body["tools"] = [
                {"type": "function",
                 "function": {"name": t.name, "description": t.description, "parameters": t.parameters}}
                for t in tool_specs
            ]
            body["tool_choice"] = "auto"

        try:
            resp = self._client.post("/chat/completions", json=body)
        except Exception as exc:  # noqa: BLE001
            raise LLMError(f"{self.base_url} call failed: {exc}") from exc
        if resp.status_code >= 400:
            raise LLMError(f"{self.base_url} returned {resp.status_code}: {resp.text[:400]}")

        data = resp.json()
        choice = (data.get("choices") or [{}])[0]
        msg = choice.get("message", {}) or {}
        calls: list[ToolCall] = []
        for tc in msg.get("tool_calls") or []:
            fn = tc.get("function", {})
            raw = fn.get("arguments") or "{}"
            try:
                args = json.loads(raw) if isinstance(raw, str) else dict(raw)
            except json.JSONDecodeError:
                args = {"_raw": raw}
            calls.append(ToolCall(id=tc.get("id") or fn.get("name", "call"), name=fn.get("name", ""), arguments=args))

        usage_raw = data.get("usage") or {}
        finish = choice.get("finish_reason") or ("tool_calls" if calls else "stop")
        return LLMResponse(
            text=(msg.get("content") or "").strip(),
            tool_calls=tuple(calls),
            usage=Usage(usage_raw.get("prompt_tokens", 0) or 0, usage_raw.get("completion_tokens", 0) or 0),
            stop_reason={"tool_calls": "tool_use", "stop": "end_turn", "length": "max_tokens"}.get(finish, finish),
            raw=data,
        )


def _to_openai_message(m: Message) -> dict[str, Any]:
    if m.role == "tool":
        return {"role": "tool", "tool_call_id": m.tool_call_id, "content": m.content}
    if m.role == "assistant" and m.tool_calls:
        return {
            "role": "assistant",
            "content": m.content or None,
            "tool_calls": [
                {"id": tc.id, "type": "function",
                 "function": {"name": tc.name, "arguments": json.dumps(tc.arguments)}}
                for tc in m.tool_calls
            ],
        }
    return {"role": m.role, "content": m.content}


# --------------------------------------------------------------------------
# Factory
# --------------------------------------------------------------------------

# provider -> (base_url, api-key env var, default free model)
_PROVIDERS = {
    "groq": ("https://api.groq.com/openai/v1", "GROQ_API_KEY", "llama-3.3-70b-versatile"),
    "openrouter": ("https://openrouter.ai/api/v1", "OPENROUTER_API_KEY", "meta-llama/llama-3.3-70b-instruct:free"),
    "cerebras": ("https://api.cerebras.ai/v1", "CEREBRAS_API_KEY", "llama-3.3-70b"),
    "ollama": ("http://localhost:11434/v1", "", "llama3.1"),
    "openai": ("https://api.openai.com/v1", "OPENAI_API_KEY", "gpt-4o-mini"),
}


def llm_from_env(model: str | None = None, **kwargs: Any) -> LLMClient:
    provider = (os.environ.get("BENCH_LLM_PROVIDER") or "").strip().lower()
    model = model or os.environ.get("BENCH_LLM_MODEL") or ""

    # explicit OpenAI-compatible endpoint
    base_url = os.environ.get("BENCH_LLM_BASE_URL")
    if provider in _PROVIDERS or base_url:
        if provider in _PROVIDERS:
            default_base, key_var, default_model = _PROVIDERS[provider]
            base_url = base_url or default_base
            api_key = os.environ.get("BENCH_LLM_API_KEY") or (os.environ.get(key_var) if key_var else None)
            model = model or default_model
        else:
            api_key = os.environ.get("BENCH_LLM_API_KEY")
            model = model or "gpt-4o-mini"
        return OpenAICompatLLM(model, base_url=base_url, api_key=api_key, **kwargs)

    model = model or "claude-sonnet-5"
    lowered = model.lower()
    if provider == "anthropic" or lowered.startswith(("claude", "anthropic")):
        return AnthropicLLM(model, **kwargs)
    if provider == "gemini" or lowered.startswith(("gemini", "google")):
        return GeminiLLM(model, **kwargs)
    raise LLMError(
        f"cannot infer a provider for model {model!r}. Set BENCH_LLM_PROVIDER "
        f"(one of: {', '.join(sorted(_PROVIDERS))}, anthropic, gemini)."
    )


def tool_result_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, default=str)


__all__ = [
    "LLMClient", "LLMResponse", "Message", "ToolSpec", "ToolCall", "Usage", "LLMError",
    "AnthropicLLM", "GeminiLLM", "OpenAICompatLLM", "FakeLLM", "llm_from_env",
]
