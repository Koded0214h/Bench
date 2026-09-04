from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from bench.agents import ToolRegistry
from bench.agents.llm import LLMResponse, ToolCall, Usage


# --- LLM response helpers ------------------------------------------------

def say(text: str) -> LLMResponse:
    return LLMResponse(text=text, usage=Usage(8, 4))


def call(name: str, args: dict[str, Any], *, cid: str = "c1", text: str = "") -> LLMResponse:
    return LLMResponse(text=text, tool_calls=(ToolCall(cid, name, args),), stop_reason="tool_use",
                       usage=Usage(8, 6))


def calls(*pairs: tuple[str, dict]) -> LLMResponse:
    tcs = tuple(ToolCall(f"c{i}", n, a) for i, (n, a) in enumerate(pairs))
    return LLMResponse(tool_calls=tcs, stop_reason="tool_use", usage=Usage(8, 6))


# --- fake Solari machine handles --------------------------------------

class FakeSandboxHandle:
    def __init__(self) -> None:
        self.id = "sbx_fake"
        self.closed = False
        self.commands: list[str] = []
        self.files: dict[str, str] = {}

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.closed = True

    def exec(self, cmd, *, args=None, cwd=None, env=None, timeout_ms=None, background=False):
        line = " ".join([cmd, *(args or [])])
        self.commands.append(line)
        if cmd == "false":
            return SimpleNamespace(exitCode=1, stdout="", stderr="boom")
        return SimpleNamespace(exitCode=0, stdout=f"ran: {line}", stderr="")

    def write_text(self, path, data):
        self.files[path] = data

    def read_text(self, path):
        return self.files.get(path, "")

    def preview_url(self, port):
        return f"https://sbx_fake-{port}.preview.getsolari.com"


class FakeBrowserHandle:
    def __init__(self) -> None:
        self.id = "ses_fake"
        self.ws_endpoint = "wss://gw.getsolari.com/ws/ses_fake"
        self.cdp_endpoint = "wss://gw.getsolari.com/cdp/ses_fake"
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.closed = True


class FakeSolari:
    def __init__(self, *, fail_launch: bool = False) -> None:
        self.fail_launch = fail_launch
        self.sandboxes: list[FakeSandboxHandle] = []
        self.browsers: list[FakeBrowserHandle] = []
        self.browser_kwargs: list[dict] = []

    def launch_sandbox(self, **kw):
        if self.fail_launch:
            raise RuntimeError("no capacity")
        h = FakeSandboxHandle()
        self.sandboxes.append(h)
        return h

    def launch_browser(self, **kw):
        if self.fail_launch:
            raise RuntimeError("no capacity")
        self.browser_kwargs.append(kw)
        h = FakeBrowserHandle()
        self.browsers.append(h)
        return h


class FakeToolset:
    """Stand-in for BrowserToolset: records actions, exposes navigate/read_page."""

    instances: list["FakeToolset"] = []

    def __init__(self, ws_endpoint: str, *, read_only: bool = False, **_kw) -> None:
        self.ws_endpoint = ws_endpoint
        self.read_only = read_only
        self.closed = False
        self.actions: list[str] = []
        FakeToolset.instances.append(self)

    def registry(self) -> ToolRegistry:
        from bench.agents import obj_schema

        reg = ToolRegistry()
        reg.tool(name="navigate", description="go", parameters=obj_schema({"url": {"type": "string"}}))(
            lambda url: self._do(f"navigate:{url}", {"url": url})
        )
        reg.tool(name="read_page", description="read", parameters=obj_schema({}))(
            lambda: self._do("read_page", {"text": "hello world", "title": "T"})
        )
        if not self.read_only:
            reg.tool(name="fill", description="fill",
                     parameters=obj_schema({"selector": {"type": "string"}, "text": {"type": "string"}}))(
                lambda selector, text: self._do(f"fill:{selector}={text}", {"ok": True})
            )
        return reg

    def _do(self, label, ret):
        self.actions.append(label)
        return ret

    def close(self):
        self.closed = True


@pytest.fixture(autouse=True)
def _reset_toolset_instances():
    FakeToolset.instances.clear()
    yield
    FakeToolset.instances.clear()
