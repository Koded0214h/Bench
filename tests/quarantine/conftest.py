from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Callable

import pytest


class FakeQBox:
    """A fake SandboxHandle: records writes, delegates exec to a callable."""

    def __init__(self, on_exec: Callable[[str, list[str], str], tuple[int, str, str]] | None = None) -> None:
        self.id = "qsbx_fake"
        self.closed = False
        self.files: dict[str, str] = {}
        self.execs: list[tuple[str, list[str]]] = []
        self._on_exec = on_exec or (lambda cmd, args, joined: (0, "", ""))

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.closed = True

    def exec(self, cmd, *, args=None, cwd=None, env=None, timeout_ms=None, background=False):
        args = list(args or [])
        self.execs.append((cmd, args))
        code, out, err = self._on_exec(cmd, args, " ".join([cmd, *args]))
        return SimpleNamespace(exitCode=code, stdout=out, stderr=err)

    def write_text(self, path, data):
        self.files[path] = data

    def read_text(self, path):
        if path not in self.files:
            raise FileNotFoundError(path)
        return self.files[path]

    def recording(self):
        return SimpleNamespace(id="rec_q_fake")


class FakeSolari:
    def __init__(self, box: FakeQBox | None = None, *, fail: bool = False) -> None:
        self._box = box or FakeQBox()
        self.fail = fail
        self.launched: list[dict] = []

    def launch_sandbox(self, **kw):
        if self.fail:
            raise RuntimeError("no capacity")
        self.launched.append(kw)
        return self._box


@pytest.fixture
def qbox() -> FakeQBox:
    return FakeQBox()


@pytest.fixture
def solari(qbox: FakeQBox) -> FakeSolari:
    return FakeSolari(qbox)
