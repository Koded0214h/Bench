"""Synchronous, teardown-guaranteed handles over the Solari SDK session objects.

Bench workers are ephemeral: one machine, one job, destroyed on completion. Every
handle here is a context manager whose ``__exit__`` runs the correct terminal
call for its machine kind, so a worker that returns — or raises — never leaks a
VM or a browser slot.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Callable

from ._loop import LoopThread


class MachineKind(str, Enum):
    BROWSER = "browser"
    SANDBOX = "sandbox"
    DESKTOP = "desktop"


class _BaseHandle:
    """Common lifecycle: run coroutines on the shared loop, tear down once."""

    kind: MachineKind

    def __init__(self, loop: LoopThread, *, teardown: Callable[[], Any], call_timeout_s: float) -> None:
        self._loop = loop
        self._teardown = teardown
        self._call_timeout_s = call_timeout_s
        self._closed = False

    def _run(self, coro: Any, *, timeout: float | None = -1.0) -> Any:
        # timeout=-1 sentinel -> use the per-call default; None -> no timeout.
        t = self._call_timeout_s if timeout == -1.0 else timeout
        return self._loop.run(coro, timeout=t)

    @property
    def closed(self) -> bool:
        return self._closed

    def close(self) -> None:
        """Destroy the machine. Idempotent; never raises."""

        if self._closed:
            return
        self._closed = True
        try:
            self._run(self._teardown(), timeout=30.0)
        except Exception:  # noqa: BLE001 - teardown is best-effort by contract
            pass

    def __enter__(self):  # type: ignore[no-untyped-def]
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


class SandboxHandle(_BaseHandle):
    """A Linux micro-VM for running model-generated code."""

    kind = MachineKind.SANDBOX

    def __init__(self, loop: LoopThread, sandbox: Any, *, teardown: Callable[[], Any], call_timeout_s: float) -> None:
        super().__init__(loop, teardown=teardown, call_timeout_s=call_timeout_s)
        self._sandbox = sandbox

    @property
    def raw(self) -> Any:
        """The underlying ``solari_core.Sandbox`` — for calls not wrapped here."""

        return self._sandbox

    @property
    def id(self) -> str:
        return self._sandbox.sandboxId

    @property
    def expires_at(self) -> str:
        return self._sandbox.expiresAt

    # -- code / commands ------------------------------------------------

    def exec(
        self,
        cmd: str,
        *,
        args: list[str] | None = None,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        timeout_ms: int | None = None,
        background: bool = False,
    ) -> Any:
        """Run a command to completion. ``cmd``+``args`` is NOT shell-parsed —
        for shell syntax use ``exec("sh", args=["-c", "..."])``. Returns a
        ``CommandResult`` (``.exitCode``, ``.stdout``, ``.stderr``)."""

        return self._run(
            self._sandbox.commands.run(
                cmd, args=args, cwd=cwd, env=env, timeout_ms=timeout_ms, background=background
            ),
            timeout=None if background else -1.0,
        )

    def run_code(self, code: str, *, language: str | None = None, context_id: str | None = None) -> Any:
        """Run code in a stateful kernel. Returns a ``RunCodeResult``."""

        return self._run(self._sandbox.run_code(code, language=language, context_id=context_id))

    def create_code_context(self, language: str = "python") -> str:
        return self._run(self._sandbox.create_code_context(language))

    # -- files -------------------------------------------------------

    def read_text(self, path: str) -> str:
        return self._run(self._sandbox.files.read_text(path))

    def write_text(self, path: str, data: str) -> None:
        self._run(self._sandbox.files.write(path, data))

    def read_bytes(self, path: str) -> bytes:
        return self._run(self._sandbox.files.read(path))

    # -- exposure / persistence ----------------------------------

    def preview_url(self, port: int) -> str:
        """Public URL that proxies to ``port`` inside the sandbox."""

        result = self._run(self._sandbox.preview_url(port))
        return str(result.get("url", "")) if isinstance(result, dict) else str(result)

    def snapshot(self, name: str | None = None) -> str:
        """Snapshot the disk/state; returns the snapshot id."""

        return self._run(self._sandbox.snapshot(name))

    def set_timeout(self, timeout_ms: int) -> Any:
        return self._run(self._sandbox.set_timeout(timeout_ms))


class DesktopHandle(_BaseHandle):
    """A sandbox with a screen — X11 plus a live stream — for computer-use."""

    kind = MachineKind.DESKTOP

    def __init__(self, loop: LoopThread, desktop: Any, *, teardown: Callable[[], Any], call_timeout_s: float) -> None:
        super().__init__(loop, teardown=teardown, call_timeout_s=call_timeout_s)
        self._desktop = desktop

    @property
    def raw(self) -> Any:
        """The underlying ``solari_core.Desktop`` — for the full action API."""

        return self._desktop

    @property
    def id(self) -> str:
        return self._desktop.sessionId

    @property
    def stream_url(self) -> str:
        return getattr(self._desktop, "streamUrl", "")

    def health(self) -> Any:
        return self._run(self._desktop.health())

    def wait_ready(self, *, timeout_s: float, poll_interval_s: float, sleep: Callable[[float], None]) -> None:
        import time as _time

        deadline = _time.monotonic() + timeout_s
        while True:
            try:
                if getattr(self.health(), "ready", False):
                    return
            except Exception:  # noqa: BLE001 - not up yet
                pass
            if _time.monotonic() >= deadline:
                raise TimeoutError(f"desktop {self.id} not ready after {timeout_s}s")
            sleep(poll_interval_s)

    def open(self, name: str, args: list[str] | None = None) -> int:
        return self._run(self._desktop.open(name, args))

    def exec(self, cmd: str, args: list[str] | None = None, **kw: Any) -> Any:
        return self._run(self._desktop.exec(cmd, args=args, **kw))

    def screenshot(self, *, fmt: str = "png") -> bytes:
        return self._run(self._desktop.screenshot(format=fmt))

    def click(self, x: int, y: int, *, humanize: bool | None = None, button: str | None = None) -> None:
        self._run(self._desktop.mouse.click(x, y, humanize=humanize, button=button))

    def type_text(self, text: str) -> None:
        self._run(self._desktop.keyboard.type(text))

    def press(self, keys: str | list[str]) -> None:
        self._run(self._desktop.keyboard.press(keys))


class BrowserHandle(_BaseHandle):
    """A cloud Chromium session. Bench owns its lifecycle; the caller drives it
    over the Playwright wire protocol / CDP using :attr:`ws_endpoint` /
    :attr:`cdp_endpoint`."""

    kind = MachineKind.BROWSER

    def __init__(
        self,
        loop: LoopThread,
        session: Any,
        sessions_resource: Any,
        *,
        teardown: Callable[[], Any],
        call_timeout_s: float,
    ) -> None:
        super().__init__(loop, teardown=teardown, call_timeout_s=call_timeout_s)
        self._session = session
        self._sessions = sessions_resource

    @property
    def raw(self) -> Any:
        return self._session

    @property
    def id(self) -> str:
        return self._session.id

    @property
    def ws_endpoint(self) -> str:
        return self._session.ws_endpoint

    @property
    def cdp_endpoint(self) -> str:
        return self._session.cdp_endpoint

    @property
    def expires_at(self) -> str:
        return self._session.expires_at

    def get_replay_url(self) -> Any:
        return self._run(self._sessions.get_replay_url(self.id))

    def download_replay(self) -> bytes:
        """Session recording as rrweb NDJSON bytes. Only if launched with
        ``recording=True``; available a few seconds after the session is
        released."""

        return self._run(self._sessions.download_replay(self.id), timeout=60.0)

    def release_and_wait(self) -> None:
        """Release the session and confirm it is gone (vs. best-effort ``close``)."""

        self._closed = True
        self._run(self._sessions.release_and_wait(self.id), timeout=30.0)
