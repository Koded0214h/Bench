"""Checks — the runnable assertions quarantine makes inside a clean sandbox.

Each check knows how to prove one thing actually works: a command exits 0, a file
parses, a server answers on a port. A check never raises out of ``run`` — a
failure (or an error running it) comes back as ``CheckResult(passed=False, ...)``.
"""

from __future__ import annotations

import json
import shlex
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str = ""
    duration_s: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "passed": self.passed, "detail": self.detail,
                "duration_s": round(self.duration_s, 3)}


@dataclass
class CheckContext:
    workdir: str
    env: dict[str, str] = field(default_factory=dict)


def _exit_code(r: Any) -> int:
    return int(getattr(r, "exitCode", getattr(r, "exit_code", 0)))


class Check:
    name: str

    def run(self, box: Any, ctx: CheckContext) -> CheckResult:  # pragma: no cover - abstract
        raise NotImplementedError

    def _timed(self, fn):
        t0 = time.monotonic()
        result = fn()
        result.duration_s = time.monotonic() - t0
        return result


@dataclass
class CommandCheck(Check):
    """Run a command; assert its exit code and, optionally, its output."""

    name: str
    cmd: str
    args: list[str] = field(default_factory=list)
    expect_exit: int = 0
    stdout_contains: str | None = None
    stderr_contains: str | None = None

    def run(self, box: Any, ctx: CheckContext) -> CheckResult:
        def _go() -> CheckResult:
            r = box.exec(self.cmd, args=list(self.args), cwd=ctx.workdir, env=ctx.env or None)
            code, out, err = _exit_code(r), (r.stdout or ""), (r.stderr or "")
            if code != self.expect_exit:
                return CheckResult(self.name, False,
                                   f"exit {code} (wanted {self.expect_exit}); stderr: {err[-400:]}")
            if self.stdout_contains and self.stdout_contains not in out:
                return CheckResult(self.name, False, f"stdout missing {self.stdout_contains!r}")
            if self.stderr_contains and self.stderr_contains not in err:
                return CheckResult(self.name, False, f"stderr missing {self.stderr_contains!r}")
            return CheckResult(self.name, True, f"exit {code}")
        return self._timed(_go)


@dataclass
class PythonCheck(Check):
    """Run a Python snippet; pass iff it exits 0."""

    name: str
    code: str

    def run(self, box: Any, ctx: CheckContext) -> CheckResult:
        def _go() -> CheckResult:
            path = f"{ctx.workdir.rstrip('/')}/_qcheck_{abs(hash(self.name)) % 10**8}.py"
            box.write_text(path, self.code)
            r = box.exec("python3", args=[path], cwd=ctx.workdir, env=ctx.env or None)
            code = _exit_code(r)
            ok = code == 0
            return CheckResult(self.name, ok,
                               "ok" if ok else f"exit {code}: {(r.stderr or r.stdout or '')[-400:]}")
        return self._timed(_go)


@dataclass
class FileCheck(Check):
    """Assert a file exists (and optionally contains a substring)."""

    name: str
    path: str
    contains: str | None = None

    def run(self, box: Any, ctx: CheckContext) -> CheckResult:
        def _go() -> CheckResult:
            target = self.path if self.path.startswith("/") else f"{ctx.workdir.rstrip('/')}/{self.path}"
            try:
                body = box.read_text(target)
            except Exception as exc:  # noqa: BLE001
                return CheckResult(self.name, False, f"cannot read {target}: {exc}")
            if self.contains is not None and self.contains not in body:
                return CheckResult(self.name, False, f"{target} missing {self.contains!r}")
            return CheckResult(self.name, True, f"{target} ok ({len(body)} bytes)")
        return self._timed(_go)


@dataclass
class ParsesCheck(Check):
    """Assert a data file parses as json / csv / yaml."""

    name: str
    path: str
    fmt: str = "json"

    _SNIPPET = {
        "json": "import json,sys; json.load(open(sys.argv[1])); print('ok')",
        "yaml": "import yaml,sys; yaml.safe_load(open(sys.argv[1])); print('ok')",
        "csv": "import csv,sys; rows=list(csv.reader(open(sys.argv[1]))); assert rows; print(len(rows))",
    }

    def run(self, box: Any, ctx: CheckContext) -> CheckResult:
        def _go() -> CheckResult:
            snippet = self._SNIPPET.get(self.fmt)
            if snippet is None:
                return CheckResult(self.name, False, f"unknown format {self.fmt!r}")
            target = self.path if self.path.startswith("/") else f"{ctx.workdir.rstrip('/')}/{self.path}"
            r = box.exec("python3", args=["-c", snippet, target], cwd=ctx.workdir)
            ok = _exit_code(r) == 0
            return CheckResult(self.name, ok,
                               (r.stdout or "").strip() if ok else (r.stderr or "")[-400:])
        return self._timed(_go)


_POLL_PY = r"""
import sys, time, urllib.request
url, deadline = sys.argv[1], time.time() + float(sys.argv[2])
last = "no attempt"
while time.time() < deadline:
    try:
        r = urllib.request.urlopen(url, timeout=3)
        body = r.read(4000).decode("utf-8", "replace")
        print(getattr(r, "status", r.getcode()))
        print(body)
        sys.exit(0)
    except Exception as e:  # noqa
        last = repr(e)
        time.sleep(1)
print("000")
print(last)
sys.exit(1)
"""


@dataclass
class HttpServesCheck(Check):
    """Start a server in the background, then assert it answers on a port."""

    name: str
    start: list[str]                 # argv, e.g. ["python3", "-m", "http.server", "8000"]
    port: int
    path: str = "/"
    expect_status: int = 200
    body_contains: str | None = None
    boot_timeout_s: int = 20

    def run(self, box: Any, ctx: CheckContext) -> CheckResult:
        def _go() -> CheckResult:
            start = " ".join(shlex.quote(p) for p in self.start)
            box.exec("sh", args=["-c", f"cd {shlex.quote(ctx.workdir)} && nohup {start} "
                                       f">/tmp/qserver.log 2>&1 & echo $! > /tmp/qserver.pid"])
            box.write_text("/tmp/_qpoll.py", _POLL_PY)
            r = box.exec("python3", args=["/tmp/_qpoll.py",
                                          f"http://localhost:{self.port}{self.path}",
                                          str(self.boot_timeout_s)])
            out = (r.stdout or "").splitlines()
            status = out[0].strip() if out else "000"
            body = "\n".join(out[1:])
            if status != str(self.expect_status):
                log = (box.exec("sh", args=["-c", "tail -20 /tmp/qserver.log 2>/dev/null"]).stdout or "")
                return CheckResult(self.name, False,
                                   f"got HTTP {status} (wanted {self.expect_status}); server log: {log[-400:]}")
            if self.body_contains and self.body_contains not in body:
                return CheckResult(self.name, False, f"body missing {self.body_contains!r}")
            return CheckResult(self.name, True, f"HTTP {status}, {len(body)} bytes")
        return self._timed(_go)


def check_from_dict(data: dict[str, Any]) -> Check:
    kind = data.get("type")
    payload = {k: v for k, v in data.items() if k != "type"}
    table = {
        "command": CommandCheck, "python": PythonCheck, "file": FileCheck,
        "parses": ParsesCheck, "http": HttpServesCheck,
    }
    cls = table.get(kind)
    if cls is None:
        raise ValueError(f"unknown check type {kind!r}; expected one of {sorted(table)}")
    return cls(**payload)


__all__ = [
    "Check", "CheckResult", "CheckContext",
    "CommandCheck", "PythonCheck", "FileCheck", "ParsesCheck", "HttpServesCheck",
    "check_from_dict",
]
