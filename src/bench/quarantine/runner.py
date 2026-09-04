"""``Quarantine`` — rebuild worker output in a clean sandbox and prove it works.

Agent output does not go straight into the company. It comes here first: a fresh
Solari sandbox, the files laid down from data (never a snapshot of the possibly-
compromised worker machine), setup commands run, then the checks. Only output
that passes is cleared to merge; everything else comes back with the failure
attached.
"""

from __future__ import annotations

import time
from typing import Any, Callable

from .checks import CheckContext, CheckResult
from .config import QuarantineConfig
from .models import QuarantineResult
from .spec import QuarantineSpec

OnEvent = Callable[[str, dict], None]


def _exit_code(r: Any) -> int:
    return int(getattr(r, "exitCode", getattr(r, "exit_code", 0)))


class Quarantine:
    def __init__(
        self,
        solari: Any,
        *,
        config: QuarantineConfig | None = None,
        on_event: OnEvent | None = None,
    ) -> None:
        self.solari = solari
        self.config = config or QuarantineConfig()
        self._on_event = on_event

    @classmethod
    def from_env(cls, solari: Any, *, on_event: OnEvent | None = None, **overrides: object) -> "Quarantine":
        return cls(solari, config=QuarantineConfig.from_env(**overrides), on_event=on_event)

    @property
    def enabled(self) -> bool:
        return self.config.enabled

    def _emit(self, kind: str, **detail: Any) -> None:
        if self._on_event:
            self._on_event(kind, detail)

    def run(self, spec: QuarantineSpec) -> QuarantineResult:
        if not self.config.enabled:
            self._emit("skipped")
            return QuarantineResult(passed=True, skipped=True)

        started = time.monotonic()
        self._emit("start", files=len(spec.files), setup=len(spec.setup), checks=len(spec.checks))
        try:
            handle = self.solari.launch_sandbox(
                template=self.config.template, timeout_ms=self.config.timeout_ms
            )
        except Exception as exc:  # noqa: BLE001
            return QuarantineResult(passed=False, failure=f"could not launch quarantine sandbox: {exc}",
                                    duration_s=time.monotonic() - started)

        with handle:
            ctx = CheckContext(workdir=spec.workdir, env=dict(spec.env))
            result = QuarantineResult(passed=False, sandbox_id=getattr(handle, "id", None))

            # 1. lay down the files
            handle.exec("mkdir", args=["-p", spec.workdir])
            for rel, content in spec.files.items():
                target = rel if rel.startswith("/") else f"{spec.workdir.rstrip('/')}/{rel}"
                parent = target.rsplit("/", 1)[0]
                if parent:
                    handle.exec("mkdir", args=["-p", parent])
                handle.write_text(target, content)
            for rel, raw in spec.binary_files.items():
                target = rel if rel.startswith("/") else f"{spec.workdir.rstrip('/')}/{rel}"
                parent = target.rsplit("/", 1)[0]
                if parent:
                    handle.exec("mkdir", args=["-p", parent])
                handle.write_bytes(target, raw)
            self._emit("materialized", files=len(spec.files) + len(spec.binary_files))

            # 2. setup commands — a failure here short-circuits
            for cmd in spec.setup:
                r = handle.exec(cmd[0], args=list(cmd[1:]), cwd=spec.workdir, env=spec.env or None,
                                timeout_ms=self.config.setup_timeout_s * 1000)
                entry = {"cmd": cmd, "exit_code": _exit_code(r),
                         "stdout": (r.stdout or "")[-2000:], "stderr": (r.stderr or "")[-2000:]}
                result.setup_log.append(entry)
                self._emit("setup", **entry)
                if _exit_code(r) != 0:
                    result.failure = f"setup failed: `{' '.join(cmd)}` exited {_exit_code(r)}\n{(r.stderr or r.stdout or '')[-800:]}"
                    result.duration_s = time.monotonic() - started
                    result.recording_id = _recording_id(handle)
                    return result

            # 3. checks
            if not spec.checks:
                result.failure = "nothing to verify: the spec has no checks"
                result.duration_s = time.monotonic() - started
                result.recording_id = _recording_id(handle)
                return result

            for check in spec.checks:
                try:
                    cr = check.run(handle, ctx)
                except Exception as exc:  # noqa: BLE001 - a check must never crash quarantine
                    cr = CheckResult(getattr(check, "name", check.__class__.__name__), False,
                                     f"check errored: {type(exc).__name__}: {exc}")
                result.checks.append(cr)
                self._emit("check", name=cr.name, passed=cr.passed, detail=cr.detail)

            result.passed = all(c.passed for c in result.checks)
            if not result.passed:
                fails = [c for c in result.checks if not c.passed]
                result.failure = "; ".join(f"{c.name}: {c.detail}" for c in fails)
            result.recording_id = _recording_id(handle)
            result.duration_s = time.monotonic() - started
            self._emit("done", passed=result.passed, summary=result.summary())
            return result

    def run_bundle(
        self,
        files: dict[str, str],
        *,
        checks: list | None = None,
        setup: list[list[str]] | None = None,
        workdir: str = "/workspace",
    ) -> QuarantineResult:
        return self.run(QuarantineSpec(files=files, checks=list(checks or []),
                                       setup=list(setup or []), workdir=workdir))


def _recording_id(handle: Any) -> str | None:
    try:
        rec = handle.recording()
    except Exception:  # noqa: BLE001
        return None
    return getattr(rec, "id", None)


__all__ = ["Quarantine"]
