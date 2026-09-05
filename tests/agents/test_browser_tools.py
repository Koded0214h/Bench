"""BrowserToolset had zero direct test coverage before — these guard the two
timeout fixes (connect() and navigate()) that stop a task hanging forever
against a dead session, and the read_only tool-gating that ResearchWorker
depends on."""

from __future__ import annotations

from bench.agents.browser_tools import _CONNECT_TIMEOUT_MS, _NAV_TIMEOUT_MS, BrowserToolset


class FakePage:
    def __init__(self):
        self.goto_calls: list[dict] = []
        self.url = "https://example.com"

    def goto(self, url, *, wait_until=None, timeout=None):
        self.goto_calls.append({"url": url, "wait_until": wait_until, "timeout": timeout})
        self.url = url

    def title(self):
        return "Example"

    def inner_text(self, selector):
        return "page text"


class FakeContext:
    def __init__(self, page):
        self.pages = [page]

    def new_page(self):
        return self.pages[0]


class FakeBrowser:
    def __init__(self, page):
        self.contexts = [FakeContext(page)]
        self.closed = False

    def close(self):
        self.closed = True


class FakeChromium:
    def __init__(self, browser):
        self._browser = browser
        self.connect_calls: list[dict] = []

    def connect(self, ws_endpoint, *, timeout=None):
        self.connect_calls.append({"ws_endpoint": ws_endpoint, "timeout": timeout})
        return self._browser


class FakePlaywright:
    def __init__(self):
        self.page = FakePage()
        self.browser = FakeBrowser(self.page)
        self.chromium = FakeChromium(self.browser)

    def stop(self):
        pass


def test_connect_passes_an_explicit_timeout():
    """A dead/expired session must not hang the worker's thread forever."""
    pw = FakePlaywright()
    BrowserToolset("wss://fake", playwright=pw)
    assert pw.chromium.connect_calls == [{"ws_endpoint": "wss://fake", "timeout": _CONNECT_TIMEOUT_MS}]


def test_navigate_passes_an_explicit_timeout_and_lighter_default_wait():
    pw = FakePlaywright()
    toolset = BrowserToolset("wss://fake", playwright=pw)
    toolset.navigate("https://example.com")
    call = pw.page.goto_calls[0]
    assert call["timeout"] == _NAV_TIMEOUT_MS
    # domcontentloaded, not load/networkidle — modern SPAs often never go
    # fully idle, which would burn the whole timeout on every navigation.
    assert call["wait_until"] == "domcontentloaded"


def test_navigate_lets_caller_override_wait_until():
    pw = FakePlaywright()
    toolset = BrowserToolset("wss://fake", playwright=pw)
    toolset.navigate("https://example.com", wait_until="load")
    assert pw.page.goto_calls[0]["wait_until"] == "load"


def test_read_only_toolset_has_no_write_capable_tools():
    pw = FakePlaywright()
    toolset = BrowserToolset("wss://fake", playwright=pw, read_only=True)
    names = set(toolset.registry().names())
    assert "click" not in names and "fill" not in names and "press" not in names
    assert "navigate" in names  # reading is still allowed


def test_non_read_only_toolset_has_write_tools():
    pw = FakePlaywright()
    toolset = BrowserToolset("wss://fake", playwright=pw, read_only=False)
    names = set(toolset.registry().names())
    assert {"click", "fill", "navigate"} <= names
