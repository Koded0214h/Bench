"""A private background event loop.

The three Solari SDKs are async (``solari-browser`` is async-only — it speaks the
Playwright wire protocol). Bench's orchestration layer is synchronous, so this
module owns one asyncio loop on a daemon thread and runs every SDK coroutine on
it. All SDK objects are created and used on this single loop, which keeps their
lazily-created ``httpx.AsyncClient`` / websocket state on one thread.
"""

from __future__ import annotations

import asyncio
import threading
from typing import Any, Awaitable, TypeVar

T = TypeVar("T")


class LoopThread:
    """Owns a daemon-threaded asyncio loop and runs coroutines on it to completion."""

    def __init__(self) -> None:
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(
            target=self._loop.run_forever, name="bench-solari-loop", daemon=True
        )
        self._thread.start()
        self._closed = False

    @property
    def loop(self) -> asyncio.AbstractEventLoop:
        return self._loop

    def run(self, coro: Awaitable[T], *, timeout: float | None = None) -> T:
        """Submit ``coro`` to the loop and block until it returns or raises.

        A ``timeout`` (seconds) that elapses raises :class:`concurrent.futures.TimeoutError`
        and cancels the coroutine.
        """

        if self._closed:
            raise RuntimeError("LoopThread is closed")
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        try:
            return future.result(timeout)
        except BaseException:
            future.cancel()
            raise

    def close(self) -> None:
        """Stop the loop and join the thread. Idempotent."""

        if self._closed:
            return
        self._closed = True
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(timeout=5)
        # Drain anything still pending, then close.
        try:
            self._loop.call_soon_threadsafe(lambda: None)
        except RuntimeError:
            pass
        if not self._loop.is_running():
            self._loop.close()

    def __enter__(self) -> "LoopThread":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()
