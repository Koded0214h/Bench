from __future__ import annotations

import threading
import time

import pytest

from bench.metering import Meter, WorkerPoolFull


def meter(cap=2) -> Meter:
    return Meter(task_budget_usd=None, max_workers=cap)


def test_slots_track_active_and_available():
    m = meter(cap=3)
    a = m.acquire_worker(task_id="t", worker_id="w1")
    b = m.acquire_worker(task_id="t", worker_id="w2")
    assert m.active_workers == 2 and m.available_slots == 1
    a.release()
    assert m.active_workers == 1 and m.available_slots == 2
    b.release()
    assert m.active_workers == 0


def test_context_manager_releases():
    m = meter(cap=1)
    with m.acquire_worker(task_id="t"):
        assert m.available_slots == 0
    assert m.available_slots == 1


def test_non_blocking_acquire_fails_when_full():
    m = meter(cap=1)
    m.acquire_worker(task_id="t")
    assert m.try_acquire_worker(task_id="t") is None
    with pytest.raises(WorkerPoolFull):
        m.acquire_worker(task_id="t", blocking=False)


def test_blocking_acquire_times_out():
    m = meter(cap=1)
    m.acquire_worker(task_id="t")
    start = time.monotonic()
    with pytest.raises(WorkerPoolFull):
        m.acquire_worker(task_id="t", timeout=0.1)
    assert time.monotonic() - start >= 0.1


def test_blocking_acquire_waits_for_release():
    m = meter(cap=1)
    held = m.acquire_worker(task_id="t", worker_id="first")
    acquired: list[str] = []

    def waiter() -> None:
        with m.acquire_worker(task_id="t", worker_id="second"):
            acquired.append("second")

    th = threading.Thread(target=waiter)
    th.start()
    time.sleep(0.05)
    assert acquired == []          # still blocked
    held.release()
    th.join(timeout=2)
    assert acquired == ["second"]


def test_double_release_is_safe():
    m = meter(cap=1)
    slot = m.acquire_worker(task_id="t")
    slot.release()
    slot.release()  # no-op, does not over-release the semaphore
    assert m.available_slots == 1
    m.acquire_worker(task_id="t")  # still exactly one slot
    assert m.available_slots == 0


def test_cap_holds_under_thread_stampede():
    m = meter(cap=4)
    peak = 0
    peak_lock = threading.Lock()

    def job() -> None:
        nonlocal peak
        with m.acquire_worker(task_id="t"):
            with peak_lock:
                peak = max(peak, m.active_workers)
            time.sleep(0.01)

    threads = [threading.Thread(target=job) for _ in range(40)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert peak <= 4
    assert m.active_workers == 0
