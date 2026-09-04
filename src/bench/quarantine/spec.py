"""What to rebuild and what "working" means — plus inference from a worker result."""

from __future__ import annotations

import base64
from dataclasses import dataclass, field
from typing import Any

from .checks import (
    Check,
    CommandCheck,
    FileCheck,
    HttpServesCheck,
    ParsesCheck,
    PythonCheck,
    check_from_dict,
)


@dataclass
class QuarantineSpec:
    """A self-contained recipe: files to lay down, commands to run, checks to pass."""

    files: dict[str, str] = field(default_factory=dict)          # relative path -> text content
    binary_files: dict[str, bytes] = field(default_factory=dict)  # relative path -> raw bytes
    setup: list[list[str]] = field(default_factory=list)  # argv commands, run before checks
    checks: list[Check] = field(default_factory=list)
    workdir: str = "/workspace"
    env: dict[str, str] = field(default_factory=dict)

    def add_check(self, check: Check) -> "QuarantineSpec":
        self.checks.append(check)
        return self

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "QuarantineSpec":
        return cls(
            files=dict(data.get("files") or {}),
            binary_files={k: base64.b64decode(v) for k, v in (data.get("binary_files_b64") or {}).items()},
            setup=[list(c) for c in (data.get("setup") or [])],
            checks=[check_from_dict(c) for c in (data.get("checks") or [])],
            workdir=str(data.get("workdir", "/workspace")),
            env=dict(data.get("env") or {}),
        )


_TEXTY = (".py", ".txt", ".md", ".html", ".css", ".js", ".json", ".yaml", ".yml", ".csv", ".toml", ".cfg", ".ini")


def infer_spec(
    worker_result: Any,
    *,
    files: dict[str, str] | None = None,
    workdir: str = "/workspace",
) -> QuarantineSpec:
    """Best-effort spec from a WorkerResult plus a bundle of file contents.

    ``files`` maps path -> content. File contents are also read from any
    artifact whose ``meta["content"]`` (text) or ``meta["content_b64"]``
    (binary — images, zips, anything exported rather than written) is set.
    Checks are inferred from what's in the bundle and the result's artifacts;
    the orchestrator is expected to refine this.
    """

    bundle: dict[str, str] = dict(files or {})
    binaries: dict[str, bytes] = {}
    for art in getattr(worker_result, "artifacts", []):
        meta = getattr(art, "meta", {}) or {}
        if meta.get("content") is not None:
            bundle[art.value] = meta["content"]
        elif meta.get("content_b64"):
            try:
                binaries[art.value] = base64.b64decode(meta["content_b64"])
            except Exception:  # noqa: BLE001
                pass

    spec = QuarantineSpec(files=bundle, binary_files=binaries, workdir=workdir)

    if "requirements.txt" in bundle:
        spec.setup.append(["pip", "install", "-q", "-r", "requirements.txt"])
    if "package.json" in bundle:
        spec.setup.append(["npm", "install", "--silent"])

    has_url = any(getattr(a, "kind", None) == "url" for a in getattr(worker_result, "artifacts", []))
    html = next((p for p in bundle if p.endswith(".html")), None)
    if has_url and html:
        spec.add_check(HttpServesCheck(
            name="serves the page",
            start=["python3", "-m", "http.server", "8000"],
            port=8000, path="/" + (html if html != "index.html" else ""),
            body_contains=None,
        ))

    for path in bundle:
        if path.endswith(".py") and not path.startswith("_"):
            spec.add_check(PythonCheck(name=f"{path} runs", code=f"import runpy; runpy.run_path({path!r})"))
        elif path.endswith(".json"):
            spec.add_check(ParsesCheck(name=f"{path} parses", path=path, fmt="json"))
        elif path.endswith((".yaml", ".yml")):
            spec.add_check(ParsesCheck(name=f"{path} parses", path=path, fmt="yaml"))
        elif path.endswith(".csv"):
            spec.add_check(ParsesCheck(name=f"{path} parses", path=path, fmt="csv"))

    for path, raw in binaries.items():
        # A binary file can't be run or parsed as text; prove it landed intact
        # (exists, non-empty, and the byte count matches what was exported).
        target = path if path.startswith("/") else f"{workdir.rstrip('/')}/{path}"
        spec.add_check(CommandCheck(
            name=f"{path} present ({len(raw)} bytes)",
            cmd="sh", args=["-c", f"[ \"$(wc -c < {_sh_quote(target)})\" -eq {len(raw)} ]"],
        ))

    if not spec.checks and bundle:
        first = sorted(bundle)[0]
        spec.add_check(FileCheck(name=f"{first} present", path=first))

    return spec


def _sh_quote(s: str) -> str:
    return "'" + s.replace("'", "'\\''") + "'"


__all__ = ["QuarantineSpec", "infer_spec"]
