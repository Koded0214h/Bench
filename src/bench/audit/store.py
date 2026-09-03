"""Append-only storage for audit events.

The store is deliberately small: append, read, and an ``exclusive()`` lock the
log holds across "read the last event, then append the next" so the hash chain
stays intact under concurrent writers (threads, and — for the JSONL store —
processes).

There is no update or delete. That is the point.
"""

from __future__ import annotations

import contextlib
import json
import os
import threading
from pathlib import Path
from typing import Iterator, Protocol

from .events import AuditEvent


class AuditStore(Protocol):
    def exclusive(self) -> "contextlib.AbstractContextManager[None]": ...

    def last(self) -> AuditEvent | None: ...

    def append(self, event: AuditEvent) -> None: ...

    def read_all(self) -> list[AuditEvent]: ...

    def __len__(self) -> int: ...


class InMemoryAuditStore:
    """Non-persistent store for tests and dry runs."""

    def __init__(self) -> None:
        self._events: list[AuditEvent] = []
        self._lock = threading.RLock()

    @contextlib.contextmanager
    def exclusive(self) -> Iterator[None]:
        with self._lock:
            yield

    def last(self) -> AuditEvent | None:
        return self._events[-1] if self._events else None

    def append(self, event: AuditEvent) -> None:
        self._events.append(event)

    def read_all(self) -> list[AuditEvent]:
        return list(self._events)

    def __len__(self) -> int:
        return len(self._events)


class JsonlAuditStore:
    """One JSON object per line, opened append-only.

    Cross-process safety uses ``fcntl.flock`` (POSIX; the project targets
    macOS/Linux). The lock is held across the read-last/append pair via
    :meth:`exclusive`, which is what the log wraps its append in.
    """

    def __init__(self, path: str | os.PathLike[str]) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.touch(exist_ok=True)
        self._tlock = threading.RLock()

    @property
    def path(self) -> Path:
        return self._path

    @contextlib.contextmanager
    def exclusive(self) -> Iterator[None]:
        with self._tlock:
            lock_path = self._path.with_suffix(self._path.suffix + ".lock")
            with open(lock_path, "w") as handle:
                _flock(handle, exclusive=True)
                try:
                    yield
                finally:
                    _flock(handle, exclusive=False, unlock=True)

    def last(self) -> AuditEvent | None:
        last_line: str | None = None
        with open(self._path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    last_line = line
        if last_line is None:
            return None
        return AuditEvent.from_dict(json.loads(last_line))

    def append(self, event: AuditEvent) -> None:
        with open(self._path, "a", encoding="utf-8") as fh:
            fh.write(event.to_json() + "\n")
            fh.flush()
            os.fsync(fh.fileno())

    def read_all(self) -> list[AuditEvent]:
        events: list[AuditEvent] = []
        with open(self._path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    events.append(AuditEvent.from_dict(json.loads(line)))
        return events

    def __len__(self) -> int:
        with open(self._path, "r", encoding="utf-8") as fh:
            return sum(1 for line in fh if line.strip())


def _flock(handle, *, exclusive: bool, unlock: bool = False) -> None:
    try:
        import fcntl
    except ImportError:  # pragma: no cover - non-POSIX
        return
    if unlock:
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    else:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH)


__all__ = ["AuditStore", "InMemoryAuditStore", "JsonlAuditStore"]
