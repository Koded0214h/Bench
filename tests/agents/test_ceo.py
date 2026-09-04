from __future__ import annotations

import pytest

from bench.agents import CEO, Capability, FakeLLM, TaskSpec, Verdict, WorkerResult, WorkerStatus
from tests.agents.conftest import call, say


PLAN_ARGS = {
    "tasks": [
        {
            "title": "Build and serve the landing page",
            "capability": "sandbox",
            "instructions": "Write a one-page site for the fintech tool, run it, return the URL.",
            "success_criteria": ["page serves on a port", "returns a live URL"],
        },
        {
            "title": "Log the launch in Salesforce",
            "capability": "browser",
            "instructions": "Create a campaign record for the launch via the Salesforce UI.",
            "success_criteria": ["campaign record exists", "record id returned"],
            "depends_on": ["Build and serve the landing page"],
            "tool": "salesforce",
        },
    ],
    "notes": "two tasks, second waits on the first",
}


def test_decompose_parses_plan_and_resolves_dependencies():
    ceo = CEO(FakeLLM([call("submit_plan", PLAN_ARGS)]))
    plan = ceo.decompose("Launch a landing page and log it in Salesforce")

    assert len(plan) == 2
    build, log = plan.tasks
    assert build.capability is Capability.SANDBOX
    assert log.capability is Capability.BROWSER and log.tool == "salesforce"
    # depends_on was a title; resolved to the build task's id
    assert log.depends_on == [build.id]
    assert plan.ordered()[0].id == build.id


def test_decompose_raises_if_no_plan_submitted():
    ceo = CEO(FakeLLM([say("I think we should maybe consider some options")]))
    with pytest.raises(ValueError, match="did not submit a plan"):
        ceo.decompose("do something")


def test_decompose_passes_company_context():
    llm = FakeLLM([call("submit_plan", {"tasks": [PLAN_ARGS["tasks"][0]]})])
    CEO(llm, company_context="We are a fintech for Nigerian freelancers.").decompose("ship it")
    assert "Nigerian freelancers" in llm.calls[0]["messages"][-1].content


@pytest.mark.parametrize("verdict", [Verdict.ACCEPT, Verdict.REJECT, Verdict.ESCALATE])
def test_review_parses_verdict(verdict):
    ceo = CEO(FakeLLM([call("submit_review", {"verdict": verdict.value, "reason": "because"})]))
    task = TaskSpec(title="t", capability="sandbox", instructions="do it", success_criteria=["x"])
    result = WorkerResult(task.id, WorkerStatus.DONE, summary="did it")
    review = ceo.review(task, result)
    assert review.verdict is verdict and review.reason == "because"
    assert review.accepted is (verdict is Verdict.ACCEPT)


def test_review_prompt_includes_artifacts_and_criteria():
    llm = FakeLLM([call("submit_review", {"verdict": "ACCEPT", "reason": "meets criteria"})])
    task = TaskSpec(title="Landing page", capability="sandbox", instructions="build it",
                    success_criteria=["returns a live URL"])
    result = WorkerResult(task.id, WorkerStatus.DONE, summary="built",
                          artifacts=[__import__("bench.agents", fromlist=["Artifact"]).Artifact(
                              "url", "https://x-8000.preview.getsolari.com", "live site")])
    CEO(llm).review(task, result)
    prompt = llm.calls[0]["messages"][-1].content
    assert "returns a live URL" in prompt
    assert "https://x-8000.preview.getsolari.com" in prompt
