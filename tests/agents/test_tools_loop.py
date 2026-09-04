from __future__ import annotations

import pytest

from bench.agents import FakeLLM, StopReason, Tool, ToolRegistry, ToolResult, obj_schema, run_agent
from tests.agents.conftest import call, calls, say


# --- tools -------------------------------------------------------------

def test_tool_invoke_coerces_and_catches():
    t = Tool("echo", "e", obj_schema({"x": {"type": "string"}}), fn=lambda x: {"got": x})
    r = t.invoke({"x": "hi"})
    assert r.ok and r.data == {"got": "hi"}

    boom = Tool("boom", "b", obj_schema({}), fn=lambda: (_ for _ in ()).throw(ValueError("nope")))
    r2 = boom.invoke({})
    assert not r2.ok and "ValueError: nope" in r2.content


def test_tool_filters_unknown_kwargs():
    t = Tool("f", "f", obj_schema({"a": {"type": "string"}}), fn=lambda a: a)
    assert t.invoke({"a": "x", "extra": "ignored"}).content == "x"


def test_registry_rejects_dupes_and_reports_unknown():
    reg = ToolRegistry([Tool("a", "a", obj_schema({}), fn=lambda: "ok")])
    with pytest.raises(ValueError):
        reg.add(Tool("a", "a2", obj_schema({}), fn=lambda: "ok"))
    res = reg.invoke("missing", {})
    assert not res.ok and "no such tool" in res.content


# --- loop --------------------------------------------------------------

def _reg():
    reg = ToolRegistry()
    reg.tool(name="add", description="add",
             parameters=obj_schema({"a": {"type": "number"}, "b": {"type": "number"}}))(
        lambda a, b: {"sum": a + b}
    )
    reg.tool(name="finish", description="done",
             parameters=obj_schema({"answer": {"type": "string"}}), terminal=True)(lambda **k: "ok")
    return reg


def test_loop_ends_on_terminal_tool():
    llm = FakeLLM([call("add", {"a": 2, "b": 3}), call("finish", {"answer": "5"})])
    run = run_agent(llm=llm, system="s", prompt="add 2 and 3", tools=_reg(), max_steps=5)
    assert run.stopped == StopReason.TERMINAL_TOOL
    assert run.result == {"answer": "5"}
    assert run.steps == 2
    assert run.usage.total_tokens == 28  # two calls, Usage(8,6) each


def test_loop_ends_on_plain_text():
    run = run_agent(llm=FakeLLM([say("here is the answer")]), system="s", prompt="p", tools=_reg())
    assert run.stopped == StopReason.PLAIN_TEXT
    assert run.text == "here is the answer"


def test_loop_hits_step_limit():
    llm = FakeLLM([call("add", {"a": 1, "b": 1})] * 10)
    run = run_agent(llm=llm, system="s", prompt="p", tools=_reg(), max_steps=3)
    assert run.stopped == StopReason.STEP_LIMIT and run.steps == 3


def test_loop_feeds_tool_error_back():
    reg = ToolRegistry()
    reg.tool(name="div", description="divide",
             parameters=obj_schema({"a": {"type": "number"}, "b": {"type": "number"}}))(
        lambda a, b: {"q": a / b}
    )
    reg.tool(name="finish", description="d", parameters=obj_schema({}), terminal=True)(lambda **k: "ok")
    llm = FakeLLM([call("div", {"a": 1, "b": 0}), call("finish", {})])
    run = run_agent(llm=llm, system="s", prompt="p", tools=reg, max_steps=4)
    tool_results = [e for e in run.events if e.kind == "tool_result"]
    assert tool_results[0].detail["ok"] is False
    assert "ZeroDivisionError" in tool_results[0].detail["content"]
    assert run.stopped == StopReason.TERMINAL_TOOL


def test_loop_multiple_tool_calls_in_one_step():
    llm = FakeLLM([calls(("add", {"a": 1, "b": 2}), ("add", {"a": 3, "b": 4})), call("finish", {})])
    run = run_agent(llm=llm, system="s", prompt="p", tools=_reg(), max_steps=4)
    step1_results = [e for e in run.events if e.kind == "tool_result" and e.step == 1]
    assert len(step1_results) == 2 and run.steps == 2


def test_loop_reports_usage_per_call():
    seen = []
    run_agent(
        llm=FakeLLM([call("add", {"a": 1, "b": 1}), say("done")]),
        system="s", prompt="p", tools=_reg(), max_steps=4,
        on_usage=lambda model, usage: seen.append(usage.total_tokens),
    )
    assert seen == [14, 12]  # Usage(8,6) then Usage(8,4)
