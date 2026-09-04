"""Worker agents — hired per task, one machine, one job, then dismissed.

``EngineeringWorker`` gets a sandbox, ``OpsWorker`` a browser it can drive,
``ResearchWorker`` a browser it can only read. Each builds a tool set bound to
its machine, runs the agent loop, and returns a :class:`WorkerResult`. The
machine is destroyed on the way out — success or failure.
"""

from __future__ import annotations

from typing import Any, Callable

from .browser_tools import BrowserToolset
from .llm import LLMClient
from .loop import OnEvent, OnUsage, StopReason, run_agent
from .models import Artifact, Capability, TaskSpec, WorkerResult, WorkerStatus
from .tools import Tool, ToolRegistry, obj_schema

_FINISH = Tool(
    name="finish",
    description="Call when the task is complete or cannot be completed. "
    "Report every deliverable as an artifact (a live URL, a file path, a record id).",
    parameters=obj_schema(
        {
            "status": {"type": "string", "enum": ["done", "failed"]},
            "summary": {"type": "string", "description": "what you did, in 1-3 sentences"},
            "artifacts": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "kind": {"type": "string", "enum": ["url", "file", "record", "text"]},
                        "value": {"type": "string"},
                        "label": {"type": "string"},
                    },
                    "required": ["kind", "value"],
                    "additionalProperties": False,
                },
            },
        },
        required=["status", "summary"],
    ),
    fn=lambda **kw: "recorded",
    terminal=True,
)

_WORKER_SYSTEM = """\
You are a worker with exactly one task and one machine. Do the task with the
tools you have — do not describe what you would do, do it. When a deliverable
exists (a running URL, a file, a created record), call finish and report it as an
artifact. If you get stuck, call finish with status "failed" and say why.
Keep going until you call finish."""


class Worker:
    capability: Capability

    def __init__(
        self,
        llm: LLMClient,
        solari: Any,
        *,
        max_steps: int = 16,
        max_tokens: int = 4096,
        on_event: OnEvent | None = None,
        on_usage: OnUsage | None = None,
        on_machine: Callable[[Any], None] | None = None,
    ) -> None:
        self.llm = llm
        self.solari = solari
        self.max_steps = max_steps
        self.max_tokens = max_tokens
        self._on_event = on_event
        self._on_usage = on_usage
        self._on_machine = on_machine

    # subclasses implement these two
    def _launch(self, task: TaskSpec) -> Any:  # -> a handle that is a context manager
        raise NotImplementedError

    def _build_tools(self, handle: Any, task: TaskSpec) -> tuple[ToolRegistry, Callable[[], None] | None]:
        raise NotImplementedError

    # -- run --------------------------------------------------------

    def run(self, task: TaskSpec) -> WorkerResult:
        try:
            handle = self._launch(task)
        except Exception as exc:  # noqa: BLE001
            return WorkerResult(task.id, WorkerStatus.FAILED, error=f"machine launch failed: {exc}")

        if self._on_machine is not None:
            try:
                self._on_machine(handle)
            except Exception:  # noqa: BLE001
                pass

        cleanup: Callable[[], None] | None = None
        try:
            with handle:
                tools, cleanup = self._build_tools(handle, task)
                tools.add(_FINISH)
                run = run_agent(
                    llm=self.llm,
                    system=_WORKER_SYSTEM,
                    prompt=_task_prompt(task),
                    tools=tools,
                    max_steps=self.max_steps,
                    max_tokens=self.max_tokens,
                    on_event=self._on_event,
                    on_usage=self._on_usage,
                )
                return self._to_result(task, run)
        except Exception as exc:  # noqa: BLE001
            return WorkerResult(task.id, WorkerStatus.FAILED, error=f"{type(exc).__name__}: {exc}")
        finally:
            if cleanup is not None:
                try:
                    cleanup()
                except Exception:  # noqa: BLE001
                    pass

    def _to_result(self, task: TaskSpec, run: Any) -> WorkerResult:
        transcript = [{"kind": e.kind, "step": e.step, **e.detail} for e in run.events]
        usage = run.usage
        if run.result:
            arts = [
                Artifact(kind=a.get("kind", "text"), value=str(a.get("value", "")), label=a.get("label", ""))
                for a in (run.result.get("artifacts") or [])
            ]
            status = WorkerStatus.DONE if run.result.get("status", "done") == "done" else WorkerStatus.FAILED
            return WorkerResult(
                task.id, status, summary=run.result.get("summary", ""), artifacts=arts,
                steps=run.steps, usage_input_tokens=usage.input_tokens,
                usage_output_tokens=usage.output_tokens, transcript=transcript,
                error=None if status is WorkerStatus.DONE else run.result.get("summary", "worker reported failure"),
            )
        if run.stopped == StopReason.STEP_LIMIT:
            return WorkerResult(
                task.id, WorkerStatus.FAILED, error=f"step limit ({self.max_steps}) reached without finishing",
                steps=run.steps, usage_input_tokens=usage.input_tokens,
                usage_output_tokens=usage.output_tokens, transcript=transcript,
            )
        return WorkerResult(
            task.id, WorkerStatus.DONE, summary=run.text, steps=run.steps,
            usage_input_tokens=usage.input_tokens, usage_output_tokens=usage.output_tokens,
            transcript=transcript,
        )


# --------------------------------------------------------------------------

class EngineeringWorker(Worker):
    capability = Capability.SANDBOX

    def __init__(self, *args: Any, sandbox_kwargs: dict[str, Any] | None = None, **kw: Any) -> None:
        super().__init__(*args, **kw)
        self._sandbox_kwargs = sandbox_kwargs or {}

    def _launch(self, task: TaskSpec) -> Any:
        return self.solari.launch_sandbox(**self._sandbox_kwargs)

    def _build_tools(self, box: Any, task: TaskSpec):
        reg = ToolRegistry()
        self._written: dict[str, str] = {}   # path -> content, exported as artifacts

        def _write(path: str, content: str) -> dict[str, Any]:
            box.write_text(path, content)
            self._written[path] = content
            return {"wrote": path, "bytes": len(content)}

        reg.tool(
            name="run_command",
            description="Run a command in the sandbox. NOT shell-parsed — pass the program in "
            "'cmd' and its arguments in 'args'. Use cmd='sh', args=['-c', '...'] for shell syntax.",
            parameters=obj_schema(
                {
                    "cmd": {"type": "string"},
                    "args": {"type": "array", "items": {"type": "string"}},
                    "cwd": {"type": ["string", "null"]},
                    "background": {"type": "boolean"},
                },
                required=["cmd"],
            ),
        )(lambda cmd, args=None, cwd=None, background=False: _exec(box, cmd, args, cwd, background))

        reg.tool(
            name="write_file", description="Write (or overwrite) a UTF-8 text file in the sandbox.",
            parameters=obj_schema({"path": {"type": "string"}, "content": {"type": "string"}},
                                  required=["path", "content"]),
        )(_write)

        reg.tool(
            name="read_file", description="Read a UTF-8 text file from the sandbox.",
            parameters=obj_schema({"path": {"type": "string"}}, required=["path"]),
        )(lambda path: {"path": path, "content": box.read_text(path)[:8000]})

        reg.tool(
            name="preview_port",
            description="Expose a port the sandbox is listening on and return a public URL.",
            parameters=obj_schema({"port": {"type": "integer"}}, required=["port"]),
        )(lambda port: {"url": box.preview_url(int(port))})

        return reg, None

    def _to_result(self, task: TaskSpec, run: Any) -> WorkerResult:
        result = super()._to_result(task, run)

        # If a url artifact has no real URL, fill it from the last preview_port call.
        preview = None
        for ev in run.events:
            if ev.kind == "tool_result" and ev.detail.get("name") == "preview_port":
                import json as _json
                try:
                    preview = _json.loads(ev.detail.get("content", "")).get("url")
                except Exception:  # noqa: BLE001
                    pass
        for art in result.artifacts:
            if art.kind == "url" and not str(art.value).startswith("http") and preview:
                art.value = preview

        # Export the files the worker wrote so quarantine can rebuild from data.
        existing = {a.value for a in result.artifacts if a.kind == "file"}
        for path, content in getattr(self, "_written", {}).items():
            if path not in existing:
                result.artifacts.append(Artifact(kind="file", value=path, label="written",
                                                 meta={"content": content}))
        return result


def _exec(box: Any, cmd: str, args: Any, cwd: Any, background: bool) -> dict[str, Any]:
    r = box.exec(cmd, args=list(args or []), cwd=cwd, background=bool(background))
    return {
        "exit_code": getattr(r, "exitCode", getattr(r, "exit_code", 0)),
        "stdout": (r.stdout or "")[-4000:],
        "stderr": (r.stderr or "")[-2000:],
    }


# --------------------------------------------------------------------------

class _BrowserWorker(Worker):
    read_only = False

    def __init__(self, *args: Any, toolset_factory: Callable[..., BrowserToolset] = BrowserToolset,
                 browser_kwargs: dict[str, Any] | None = None, **kw: Any) -> None:
        super().__init__(*args, **kw)
        self._toolset_factory = toolset_factory
        self._browser_kwargs = browser_kwargs or {}

    def _launch(self, task: TaskSpec) -> Any:
        kwargs = dict(self._browser_kwargs)
        if task.tool and "profile" not in kwargs and "profile_id" not in kwargs:
            kwargs["profile"] = task.tool
        return self.solari.launch_browser(**kwargs)

    def _build_tools(self, handle: Any, task: TaskSpec):
        toolset = self._toolset_factory(handle.ws_endpoint, read_only=self.read_only)
        return toolset.registry(), toolset.close


class OpsWorker(_BrowserWorker):
    capability = Capability.BROWSER
    read_only = False


class ResearchWorker(_BrowserWorker):
    capability = Capability.BROWSER
    read_only = True


# --------------------------------------------------------------------------

_WORKERS: dict[Capability, type[Worker]] = {
    Capability.SANDBOX: EngineeringWorker,
    Capability.BROWSER: OpsWorker,
}


def build_worker(task: TaskSpec, llm: LLMClient, solari: Any, **kw: Any) -> Worker:
    """Pick a worker class for a task. A browser task with no `tool` and a
    read-only feel still gets OpsWorker; use ResearchWorker explicitly for
    read-only research."""

    cls = _WORKERS.get(task.capability, EngineeringWorker)
    return cls(llm, solari, **kw)


def _task_prompt(task: TaskSpec) -> str:
    lines = [f"TASK: {task.title}", "", task.instructions]
    if task.success_criteria:
        lines += ["", "Done when:"] + [f"  - {c}" for c in task.success_criteria]
    if task.context:
        lines += ["", "Context:"] + [f"  {k}: {v}" for k, v in task.context.items()]
    return "\n".join(lines)


__all__ = [
    "Worker", "EngineeringWorker", "OpsWorker", "ResearchWorker", "build_worker",
]
