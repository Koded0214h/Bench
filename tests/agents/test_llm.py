from __future__ import annotations

import pytest

from bench.agents import AnthropicLLM, FakeLLM, LLMError, Message, ToolCall, ToolSpec, Usage, llm_from_env
from bench.agents.llm import _to_anthropic_message


def test_usage_add_and_total():
    u = Usage(3, 4) + Usage(10, 1)
    assert (u.input_tokens, u.output_tokens, u.total_tokens) == (13, 5, 18)


def test_fake_llm_scripts_and_exhausts():
    fake = FakeLLM(["hello", ("", (ToolCall("c1", "finish", {"x": 1}),))])
    assert fake.complete(messages=[Message("user", "hi")]).text == "hello"
    r = fake.complete(messages=[Message("user", "again")])
    assert r.tool_calls[0].name == "finish"
    with pytest.raises(LLMError):
        fake.complete(messages=[Message("user", "more")])
    assert len(fake.calls) == 3


def test_fake_llm_callable_script():
    fake = FakeLLM(lambda messages, tools: "echo:" + messages[-1].content)
    assert fake.complete(messages=[Message("user", "ping")]).text == "echo:ping"


def test_message_mapping_tool_result():
    m = Message(role="tool", tool_call_id="c9", content="42", is_error=True)
    wire = _to_anthropic_message(m)
    assert wire["role"] == "user"
    block = wire["content"][0]
    assert block["type"] == "tool_result" and block["tool_use_id"] == "c9" and block["is_error"] is True


def test_message_mapping_assistant_tool_use():
    m = Message(role="assistant", content="thinking", tool_calls=[ToolCall("c1", "run", {"a": 1})])
    wire = _to_anthropic_message(m)
    types = [b["type"] for b in wire["content"]]
    assert types == ["text", "tool_use"]
    assert wire["content"][1]["input"] == {"a": 1}


class _FakeAnthropicClient:
    def __init__(self, blocks, *, stop="tool_use", usage=(11, 7)):
        self._blocks = blocks
        self._stop = stop
        self._usage = usage
        self.last_kwargs = None
        self.messages = self

    def create(self, **kwargs):
        self.last_kwargs = kwargs
        from types import SimpleNamespace
        return SimpleNamespace(
            content=self._blocks,
            stop_reason=self._stop,
            usage=SimpleNamespace(input_tokens=self._usage[0], output_tokens=self._usage[1]),
        )


def test_anthropic_llm_parses_text_and_tool_use():
    from types import SimpleNamespace

    blocks = [
        SimpleNamespace(type="text", text="ok, running"),
        SimpleNamespace(type="tool_use", id="tu_1", name="run_command", input={"cmd": "ls"}),
    ]
    llm = AnthropicLLM("claude-sonnet-5", client=_FakeAnthropicClient(blocks))
    resp = llm.complete(
        messages=[Message("user", "list files")],
        system="be terse",
        tools=[ToolSpec("run_command", "run", {"type": "object", "properties": {}})],
    )
    assert resp.text == "ok, running"
    assert resp.tool_calls[0].name == "run_command" and resp.tool_calls[0].arguments == {"cmd": "ls"}
    assert resp.usage == Usage(11, 7)
    assert llm._client.last_kwargs["system"] == "be terse"
    assert llm._client.last_kwargs["tools"][0]["input_schema"] == {"type": "object", "properties": {}}


def test_anthropic_llm_wraps_errors():
    class Boom:
        messages = property(lambda self: self)

        def create(self, **kw):
            raise RuntimeError("429")

    llm = AnthropicLLM("claude-sonnet-5", client=Boom())
    with pytest.raises(LLMError):
        llm.complete(messages=[Message("user", "hi")])


def test_llm_from_env_infers_provider(monkeypatch):
    for v in ("BENCH_LLM_PROVIDER", "BENCH_LLM_BASE_URL", "BENCH_LLM_MODEL", "GROQ_API_KEY"):
        monkeypatch.delenv(v, raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    assert isinstance(llm_from_env("claude-sonnet-5"), AnthropicLLM)
    with pytest.raises(LLMError):
        llm_from_env("mystery-model")


# --- OpenAI-compatible client ------------------------------------------

class _FakeHttp:
    def __init__(self, payload, status=200):
        self._payload = payload
        self._status = status
        self.last = None

    def post(self, path, json):
        self.last = {"path": path, "body": json}
        import json as _j
        from types import SimpleNamespace

        return SimpleNamespace(status_code=self._status, json=lambda: self._payload,
                               text=_j.dumps(self._payload))


def test_openai_compat_parses_text_and_tools():
    from bench.agents import OpenAICompatLLM

    payload = {
        "choices": [{
            "message": {
                "content": "on it",
                "tool_calls": [{"id": "call_1", "function": {"name": "run_command",
                                                             "arguments": '{"cmd": "ls"}'}}],
            },
            "finish_reason": "tool_calls",
        }],
        "usage": {"prompt_tokens": 12, "completion_tokens": 5},
    }
    http = _FakeHttp(payload)
    llm = OpenAICompatLLM("llama-3.3-70b", base_url="https://api.groq.com/openai/v1", client=http)
    r = llm.complete(
        messages=[Message("user", "list files")],
        system="be terse",
        tools=[ToolSpec("run_command", "run", {"type": "object", "properties": {}})],
    )
    assert r.text == "on it"
    assert r.tool_calls[0].name == "run_command" and r.tool_calls[0].arguments == {"cmd": "ls"}
    assert r.usage == Usage(12, 5) and r.stop_reason == "tool_use"
    sent = http.last["body"]
    assert sent["messages"][0] == {"role": "system", "content": "be terse"}
    assert sent["tools"][0]["function"]["name"] == "run_command"


def test_openai_compat_bad_tool_json_becomes_raw():
    from bench.agents import OpenAICompatLLM

    payload = {"choices": [{"message": {"content": "",
               "tool_calls": [{"id": "c1", "function": {"name": "x", "arguments": "not json"}}]},
               "finish_reason": "tool_calls"}], "usage": {}}
    llm = OpenAICompatLLM("m", base_url="http://x/v1", client=_FakeHttp(payload))
    r = llm.complete(messages=[Message("user", "go")])
    assert r.tool_calls[0].arguments == {"_raw": "not json"}


def test_openai_compat_http_error_wrapped():
    from bench.agents import OpenAICompatLLM

    llm = OpenAICompatLLM("m", base_url="http://x/v1", client=_FakeHttp({"error": "nope"}, status=401))
    with pytest.raises(LLMError):
        llm.complete(messages=[Message("user", "go")])


def test_llm_from_env_openai_compat_routing(monkeypatch):
    from bench.agents import OpenAICompatLLM

    for v in ("ANTHROPIC_API_KEY", "BENCH_LLM_BASE_URL", "BENCH_LLM_MODEL"):
        monkeypatch.delenv(v, raising=False)
    monkeypatch.setenv("BENCH_LLM_PROVIDER", "groq")
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test")
    llm = llm_from_env()
    assert isinstance(llm, OpenAICompatLLM)
    assert llm.base_url == "https://api.groq.com/openai/v1"
    assert llm.model == "openai/gpt-oss-120b"

    monkeypatch.setenv("BENCH_LLM_PROVIDER", "")
    monkeypatch.setenv("BENCH_LLM_BASE_URL", "http://localhost:1234/v1")
    monkeypatch.setenv("BENCH_LLM_MODEL", "local-model")
    llm2 = llm_from_env()
    assert isinstance(llm2, OpenAICompatLLM) and llm2.model == "local-model"
