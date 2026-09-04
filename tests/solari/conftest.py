"""Fakes for the three Solari SDK clients, wired in through SolariBackends.

No network, no real event-loop SDK objects — just enough async surface for the
facade in ``bench.solari.client`` to drive.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

import pytest

from bench.solari import SolariBackends, SolariClient, SolariConfig


# --- sandbox ---------------------------------------------------------------

class FakeSandbox:
    def __init__(self, sandbox_id: str, **create_kwargs: Any) -> None:
        self.sandboxId = sandbox_id
        self.expiresAt = "2026-09-03T01:00:00Z"
        self.create_kwargs = create_kwargs
        self.connected = False
        self.killed = False
        self.timeout_ms: int | None = None
        self._files: dict[str, str] = {}
        self.commands = SimpleNamespace(run=self._run_cmd)

    async def connect(self) -> None:
        self.connected = True

    async def _run_cmd(self, cmd: str, *, args=None, cwd=None, env=None, timeout_ms=None, background=False):
        joined = " ".join([cmd, *(args or [])])
        if background:
            return SimpleNamespace(exitCode=0, stdout="", stderr="")
        return SimpleNamespace(exitCode=0, stdout=f"ran: {joined}", stderr="")

    async def run_code(self, code: str, *, language=None, context_id=None):
        return SimpleNamespace(results=[SimpleNamespace(type="stdout", text=code)], error=None)

    async def create_code_context(self, language: str = "python") -> str:
        return f"ctx_{language}"

    async def preview_url(self, port: int) -> dict:
        return {"url": f"https://{self.sandboxId}-{port}.preview.getsolari.com"}

    async def snapshot(self, name: str | None = None) -> str:
        return f"snap_{self.sandboxId}"

    async def set_timeout(self, timeout_ms: int) -> dict:
        self.timeout_ms = timeout_ms
        return {"timeoutMs": timeout_ms}

    async def kill(self) -> None:
        self.killed = True

    # file surface used by the handle
    @property
    def files(self):
        outer = self

        class _F:
            async def read_text(self, path): return outer._files.get(path, "")
            async def read(self, path):
                v = outer._files.get(path, b"")
                return v if isinstance(v, bytes) else v.encode()
            async def write(self, path, data, mode=None): outer._files[path] = data

        return _F()


class FakeSandboxClient:
    def __init__(self, *, slow: float = 0.0) -> None:
        self.slow = slow
        self.created: list[FakeSandbox] = []
        self.closed = False

    async def create(self, **kwargs: Any) -> FakeSandbox:
        if self.slow:
            await asyncio.sleep(self.slow)
        sb = FakeSandbox(f"sbx_{len(self.created) + 1}", **kwargs)
        self.created.append(sb)
        return sb

    async def aclose(self) -> None:
        self.closed = True


# --- desktop --------------------------------------------------------------

class FakeDesktop:
    def __init__(self, session_id: str, ready_after: int = 0, **create_kwargs: Any) -> None:
        self.sessionId = session_id
        self.streamUrl = f"https://stream.getsolari.com/{session_id}"
        self.create_kwargs = create_kwargs
        self._ready_after = ready_after
        self._health_calls = 0
        self.closed = False
        self.actions: list[str] = []
        self.mouse = SimpleNamespace(click=self._click)
        self.keyboard = SimpleNamespace(type=self._type, press=self._press)

    async def connect(self) -> None:
        self.actions.append("connect")

    async def health(self):
        self._health_calls += 1
        return SimpleNamespace(ready=self._health_calls > self._ready_after)

    async def open(self, name, args=None) -> int:
        self.actions.append(f"open:{name}")
        return 4242

    async def exec(self, cmd, args=None, **kw):
        return SimpleNamespace(exitCode=0, stdout="", stderr="")

    async def screenshot(self, *, format="png") -> bytes:
        return b"\x89PNG-fake"

    async def _click(self, x, y, *, humanize=None, button=None):
        self.actions.append(f"click:{x},{y}")

    async def _type(self, text):
        self.actions.append(f"type:{text}")

    async def _press(self, keys):
        self.actions.append(f"press:{keys}")

    async def close(self) -> None:
        self.closed = True


class FakeDesktopClient:
    def __init__(self, *, ready_after: int = 0, never_ready: bool = False) -> None:
        self.ready_after = 10**6 if never_ready else ready_after
        self.created: list[FakeDesktop] = []
        self.destroyed: list[str] = []
        self.closed = False

    async def create(self, **kwargs: Any) -> FakeDesktop:
        d = FakeDesktop(f"dsk_{len(self.created) + 1}", ready_after=self.ready_after, **kwargs)
        self.created.append(d)
        return d

    async def destroy(self, session_id: str):
        self.destroyed.append(session_id)
        return SimpleNamespace(ok=True)

    async def aclose(self) -> None:
        self.closed = True


# --- browser --------------------------------------------------------------

class FakeSession:
    def __init__(self, session_id: str, **kw: Any) -> None:
        self.id = session_id
        self.ws_endpoint = f"wss://gw.getsolari.com/ws/{session_id}"
        self.cdp_endpoint = f"wss://gw.getsolari.com/cdp/{session_id}"
        self.expires_at = "2026-09-03T01:00:00Z"
        self.create_kwargs = kw


class _FakeSessions:
    def __init__(self, owner: "FakeBrowserClient") -> None:
        self._owner = owner

    async def create(self, **kwargs: Any) -> FakeSession:
        s = FakeSession(f"ses_{len(self._owner.sessions_made) + 1}", **kwargs)
        self._owner.sessions_made.append(s)
        return s

    async def release(self, session_id: str) -> None:
        self._owner.released.append(session_id)

    async def release_and_wait(self, session_id: str) -> None:
        self._owner.released.append(session_id)
        self._owner.confirmed_release.append(session_id)

    async def get_replay_url(self, session_id: str):
        return SimpleNamespace(url=f"https://replays.getsolari.com/{session_id}", expires_in_seconds=60)

    async def download_replay(self, session_id: str) -> bytes:
        return b'{"type":2}\n{"type":3}'


class _FakeProfiles:
    def __init__(self, owner: "FakeBrowserClient") -> None:
        self._owner = owner

    async def list(self):
        return list(self._owner.profiles_store)

    async def create(self, name: str):
        p = SimpleNamespace(id=f"prf_{len(self._owner.profiles_store) + 1}", name=name)
        self._owner.profiles_store.append(p)
        return p

    async def delete(self, profile_id: str) -> None:
        self._owner.profiles_store = [p for p in self._owner.profiles_store if p.id != profile_id]


class FakeBrowserClient:
    def __init__(self) -> None:
        self.sessions_made: list[FakeSession] = []
        self.released: list[str] = []
        self.confirmed_release: list[str] = []
        self.profiles_store: list[Any] = []
        self.closed = False
        self.sessions = _FakeSessions(self)
        self.profiles = _FakeProfiles(self)

    async def close(self) -> None:
        self.closed = True


# --- fixtures -----------------------------------------------------------

@pytest.fixture
def sandbox_backend() -> FakeSandboxClient:
    return FakeSandboxClient()


@pytest.fixture
def desktop_backend() -> FakeDesktopClient:
    return FakeDesktopClient()


@pytest.fixture
def browser_backend() -> FakeBrowserClient:
    return FakeBrowserClient()


@pytest.fixture
def config() -> SolariConfig:
    return SolariConfig(
        api_key="slr_live_test",
        launch_timeout_s=2.0,
        launch_poll_interval_s=0.0,
        call_timeout_ms=2000,
    )


@pytest.fixture
def make_client(config, sandbox_backend, desktop_backend, browser_backend):
    created: list[SolariClient] = []

    def _factory(**over: Any) -> SolariClient:
        backends = SolariBackends(
            sandbox=lambda cfg: over.get("sandbox", sandbox_backend),
            desktop=lambda cfg: over.get("desktop", desktop_backend),
            browser=lambda cfg: over.get("browser", browser_backend),
        )
        c = SolariClient(config, backends=backends, sleep=lambda _s: None)
        created.append(c)
        return c

    yield _factory
    for c in created:
        c.close()


@pytest.fixture
def client(make_client) -> SolariClient:
    return make_client()
