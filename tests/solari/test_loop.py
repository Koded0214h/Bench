from __future__ import annotations

import asyncio
from concurrent.futures import TimeoutError as FutureTimeoutError

import pytest

from bench.solari._loop import LoopThread


def test_runs_coroutine_and_returns_value():
    with LoopThread() as loop:
        assert loop.run(asyncio.sleep(0, result=42)) == 42


def test_propagates_exception():
    async def boom():
        raise ValueError("nope")

    with LoopThread() as loop:
        with pytest.raises(ValueError, match="nope"):
            loop.run(boom())


def test_timeout_raises_and_cancels():
    cancelled = {"v": False}

    async def slow():
        try:
            await asyncio.sleep(5)
        except asyncio.CancelledError:
            cancelled["v"] = True
            raise

    with LoopThread() as loop:
        with pytest.raises(FutureTimeoutError):
            loop.run(slow(), timeout=0.05)
        # give the cancellation a beat to land on the loop thread
        loop.run(asyncio.sleep(0.05))
    assert cancelled["v"] is True


def test_close_is_idempotent():
    loop = LoopThread()
    loop.close()
    loop.close()
    coro = asyncio.sleep(0)
    with pytest.raises(RuntimeError):
        loop.run(coro)
    coro.close()
