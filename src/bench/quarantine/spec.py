"""What to rebuild and what "working" means — plus inference from a worker result."""

from __future__ import annotations

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

    files: dict[str, str] = field(default_factory=dict)   # relative path -> text content
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
    ``Artifact(kind="file")`` whose ``meta["content"]`` is set. Checks are
    inferred from what's in the bundle and the result's artifacts; the
    orchestrator is expected to refine this.
    """

    bundle: dict[str, str] = dict(files or {})
    for art in getattr(worker_result, "artifacts", []):
        if getattr(art, "kind", None) == "file":
            content = (getattr(art, "meta", {}) or {}).get("content")
            if content is not None:
                bundle[art.value] = content

    spec = QuarantineSpec(files=bundle, workdir=workdir)

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

    if not spec.checks and bundle:
        first = sorted(bundle)[0]
        spec.add_check(FileCheck(name=f"{first} present", path=first))

    return spec


__all__ = ["QuarantineSpec", "infer_spec"]
