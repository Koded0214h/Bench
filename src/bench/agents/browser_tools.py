"""A minimal, real browser toolset for ops/research workers.

Connects Playwright (via patchright) to a Solari browser session over its wire
endpoint and exposes a handful of actions. Deliberately small — browser
automation against a changing UI is brittle, and a worker only needs to navigate,
read, and (for ops) click and type.
"""

from __future__ import annotations

import base64
import tempfile
from typing import Any

from .tools import ToolRegistry, obj_schema

_READ_LIMIT = 8000


class BrowserToolset:
    def __init__(self, ws_endpoint: str, *, read_only: bool = False, playwright: Any = None) -> None:
        self.read_only = read_only
        self._ws = ws_endpoint
        if playwright is not None:  # injected in tests
            self._pw = playwright
            self._owns_pw = False
        else:  # pragma: no cover - needs a live browser
            from patchright.sync_api import sync_playwright

            self._pw = sync_playwright().start()
            self._owns_pw = True
        self._browser = self._pw.chromium.connect(ws_endpoint)
        self._page = None

    # -- lifecycle --------------------------------------------------

    def _page_(self) -> Any:
        if self._page is None:
            ctx = self._browser.contexts[0] if self._browser.contexts else self._browser.new_context()
            self._page = ctx.pages[0] if ctx.pages else ctx.new_page()
        return self._page

    def close(self) -> None:
        try:
            self._browser.close()
        finally:
            if self._owns_pw:
                self._pw.stop()

    # -- actions --------------------------------------------------

    def navigate(self, url: str, wait_until: str = "load") -> dict[str, Any]:
        page = self._page_()
        page.goto(url, wait_until=wait_until)
        return {"url": page.url, "title": page.title()}

    def read_page(self) -> dict[str, Any]:
        page = self._page_()
        text = page.inner_text("body")
        return {
            "url": page.url,
            "title": page.title(),
            "text": text[:_READ_LIMIT],
            "truncated": len(text) > _READ_LIMIT,
        }

    def find_links(self, contains: str | None = None, limit: int = 40) -> dict[str, Any]:
        page = self._page_()
        links = page.eval_on_selector_all(
            "a[href]",
            "els => els.map(e => ({text: (e.innerText||'').trim().slice(0,120), href: e.href}))",
        )
        if contains:
            needle = contains.lower()
            links = [l for l in links if needle in (l["text"] + l["href"]).lower()]
        return {"links": links[:limit], "count": len(links)}

    def click(self, selector: str) -> dict[str, Any]:
        self._guard()
        page = self._page_()
        page.click(selector, timeout=10_000)
        return {"clicked": selector, "url": page.url}

    def fill(self, selector: str, text: str) -> dict[str, Any]:
        self._guard()
        page = self._page_()
        page.fill(selector, text, timeout=10_000)
        return {"filled": selector}

    def press(self, selector: str, key: str) -> dict[str, Any]:
        self._guard()
        self._page_().press(selector, key, timeout=10_000)
        return {"pressed": key, "on": selector}

    def screenshot(self) -> dict[str, Any]:
        raw = self._page_().screenshot(type="png")
        path = tempfile.mktemp(prefix="bench-shot-", suffix=".png")
        with open(path, "wb") as fh:
            fh.write(raw)
        return {"path": path, "bytes": len(raw), "b64_head": base64.b64encode(raw[:24]).decode()}

    def _guard(self) -> None:
        if self.read_only:
            raise PermissionError("this worker is read-only; click/fill/press are not available")

    # -- registry --------------------------------------------------

    def registry(self) -> ToolRegistry:
        reg = ToolRegistry()
        reg.tool(
            name="navigate", description="Load a URL in the browser.",
            parameters=obj_schema({"url": {"type": "string"}}, required=["url"]),
        )(self.navigate)
        reg.tool(
            name="read_page", description="Return the current page's visible text, title and URL.",
            parameters=obj_schema({}),
        )(self.read_page)
        reg.tool(
            name="find_links", description="List anchor links on the page, optionally filtered.",
            parameters=obj_schema(
                {"contains": {"type": ["string", "null"]}, "limit": {"type": "integer"}}, required=[],
            ),
        )(self.find_links)
        if not self.read_only:
            reg.tool(
                name="click", description="Click the element matching a CSS selector.",
                parameters=obj_schema({"selector": {"type": "string"}}, required=["selector"]),
            )(self.click)
            reg.tool(
                name="fill", description="Fill an input matching a CSS selector with text.",
                parameters=obj_schema({"selector": {"type": "string"}, "text": {"type": "string"}},
                                      required=["selector", "text"]),
            )(self.fill)
            reg.tool(
                name="press", description="Press a key (e.g. 'Enter') on an element.",
                parameters=obj_schema({"selector": {"type": "string"}, "key": {"type": "string"}},
                                      required=["selector", "key"]),
            )(self.press)
        reg.tool(
            name="screenshot", description="Capture a PNG screenshot of the page; returns a file path.",
            parameters=obj_schema({}),
        )(self.screenshot)
        return reg


__all__ = ["BrowserToolset"]
