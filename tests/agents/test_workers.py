from __future__ import annotations

from bench.agents import (
    Capability,
    EngineeringWorker,
    FakeLLM,
    OpsWorker,
    ResearchWorker,
    TaskSpec,
    WorkerStatus,
    build_worker,
)
from tests.agents.conftest import FakeSolari, FakeToolset, call, calls, say

ENG_TASK = TaskSpec(
    title="Build and serve the landing page",
    capability="sandbox",
    instructions="Write index.html, serve it on 8000, return the URL.",
    success_criteria=["serves on :8000", "returns a live URL"],
)


def test_engineering_worker_runs_tools_and_finishes():
    solari = FakeSolari()
    llm = FakeLLM([
        call("write_file", {"path": "index.html", "content": "<h1>hi</h1>"}),
        call("run_command", {"cmd": "python3", "args": ["-m", "http.server", "8000"], "background": True}),
        call("preview_port", {"port": 8000}),
        call("finish", {
            "status": "done", "summary": "served the page",
            "artifacts": [{"kind": "url", "value": "https://sbx_fake-8000.preview.getsolari.com",
                           "label": "live site"}],
        }),
    ])
    result = EngineeringWorker(llm, solari, max_steps=8).run(ENG_TASK)

    assert result.status is WorkerStatus.DONE
    assert result.artifact_urls() == ["https://sbx_fake-8000.preview.getsolari.com"]
    box = solari.sandboxes[0]
    assert box.files["index.html"] == "<h1>hi</h1>"
    assert any("http.server" in c for c in box.commands)
    assert box.closed is True                      # machine torn down
    assert result.steps == 4
    assert result.usage_input_tokens > 0


def test_engineering_worker_reports_failure_status():
    solari = FakeSolari()
    llm = FakeLLM([call("finish", {"status": "failed", "summary": "could not bind port"})])
    result = EngineeringWorker(llm, solari).run(ENG_TASK)
    assert result.status is WorkerStatus.FAILED
    assert "could not bind port" in (result.error or "")
    assert solari.sandboxes[0].closed is True


def test_worker_machine_launch_failure_is_captured():
    result = EngineeringWorker(FakeLLM([]), FakeSolari(fail_launch=True)).run(ENG_TASK)
    assert result.status is WorkerStatus.FAILED
    assert "machine launch failed" in (result.error or "")


def test_worker_step_limit_is_failure():
    solari = FakeSolari()
    llm = FakeLLM([call("run_command", {"cmd": "echo", "args": ["x"]})] * 20)
    result = EngineeringWorker(llm, solari, max_steps=3).run(ENG_TASK)
    assert result.status is WorkerStatus.FAILED and "step limit" in result.error
    assert solari.sandboxes[0].closed is True


def test_ops_worker_uses_browser_and_closes_toolset():
    solari = FakeSolari()
    task = TaskSpec(title="Log the launch", capability="browser",
                    instructions="Create a campaign record.", success_criteria=["record created"],
                    tool="salesforce")
    llm = FakeLLM([
        call("navigate", {"url": "https://salesforce.com/lightning/o/Campaign/new"}),
        call("fill", {"selector": "#name", "text": "Fintech Launch"}),
        call("finish", {"status": "done", "summary": "created campaign",
                        "artifacts": [{"kind": "record", "value": "701XX000001", "label": "campaign id"}]}),
    ])
    worker = OpsWorker(llm, solari, toolset_factory=FakeToolset, max_steps=8)
    result = worker.run(task)

    assert result.status is WorkerStatus.DONE
    assert solari.browser_kwargs[0]["profile"] == "salesforce"   # task.tool -> profile
    ts = FakeToolset.instances[0]
    assert ts.actions[0].startswith("navigate:") and any(a.startswith("fill:") for a in ts.actions)
    assert ts.closed is True
    assert solari.browsers[0].closed is True


def test_research_worker_toolset_is_read_only():
    solari = FakeSolari()
    task = TaskSpec(title="Research competitors", capability="browser",
                    instructions="Summarize three competitor pricing pages.",
                    success_criteria=["three pages summarized"])
    llm = FakeLLM([call("navigate", {"url": "https://example.com"}),
                   call("finish", {"status": "done", "summary": "read one page"})])
    ResearchWorker(llm, solari, toolset_factory=FakeToolset).run(task)
    assert FakeToolset.instances[0].read_only is True


def test_build_worker_picks_class_by_capability():
    solari = FakeSolari()
    llm = FakeLLM([])
    assert isinstance(build_worker(ENG_TASK, llm, solari), EngineeringWorker)
    browser_task = TaskSpec(title="x", capability="browser", instructions="y", success_criteria=["z"])
    assert isinstance(build_worker(browser_task, llm, solari, toolset_factory=FakeToolset), OpsWorker)


def test_export_file_embeds_bytes_on_matching_artifact():
    solari2 = FakeSolari()
    llm2 = FakeLLM([
        call("export_file", {"path": "logo.png"}),
        call("finish", {
            "status": "done", "summary": "made a logo",
            "artifacts": [{"kind": "image", "value": "https://sbx-8000.preview.getsolari.com/logo.png?t=x",
                           "label": "logo"}],
        }),
    ])
    worker = EngineeringWorker(llm2, solari2, max_steps=8)

    # seed bytes on the box the worker is about to launch
    real_launch = worker._launch
    def launch_with_bytes(task):
        box = real_launch(task)
        box.binary_files["logo.png"] = b"\x89PNG-not-real-but-bytes"
        return box
    worker._launch = launch_with_bytes

    result2 = worker.run(ENG_TASK)
    art = next(a for a in result2.artifacts if a.kind == "image")
    assert art.meta["mime"] == "image/png"
    import base64
    assert base64.b64decode(art.meta["content_b64"]) == b"\x89PNG-not-real-but-bytes"


def test_export_file_too_large_is_reported_not_crashed():
    solari = FakeSolari()
    llm = FakeLLM([call("export_file", {"path": "huge.bin"}),
                   call("finish", {"status": "failed", "summary": "file too big"})])
    worker = EngineeringWorker(llm, solari, max_steps=8)
    real_launch = worker._launch
    def launch_with_huge(task):
        box = real_launch(task)
        box.binary_files["huge.bin"] = b"x" * (5 * 1024 * 1024)
        return box
    worker._launch = launch_with_huge

    result = worker.run(ENG_TASK)
    assert result.status is WorkerStatus.FAILED  # model saw the error tool result and gave up cleanly


def test_unreferenced_exported_file_still_ships_as_artifact():
    solari = FakeSolari()
    llm = FakeLLM([call("export_file", {"path": "report.pdf"}),
                   call("finish", {"status": "done", "summary": "done", "artifacts": []})])
    worker = EngineeringWorker(llm, solari, max_steps=8)
    real_launch = worker._launch
    def launch_with_pdf(task):
        box = real_launch(task)
        box.binary_files["report.pdf"] = b"%PDF-fake"
        return box
    worker._launch = launch_with_pdf

    result = worker.run(ENG_TASK)
    art = next(a for a in result.artifacts if a.value == "report.pdf")
    assert art.kind == "file" and art.meta["mime"] == "application/pdf"
