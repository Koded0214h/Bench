"""Bench orchestration — module 7.

The LangGraph state machine that drives the task lifecycle: decompose → policy
check → hire → work → quarantine → review → dismiss, with a bounded retry budget
that escalates rather than looping.

    from bench.orchestration import Orchestrator
    from bench.agents import llm_from_env
    from bench.solari import SolariClient
    from bench.policy import PolicyEngine
    from bench.metering import Meter
    from bench.audit import AuditLog
    from bench.quarantine import Quarantine

    with SolariClient.from_env() as solari:
        orch = Orchestrator(
            llm=llm_from_env(), solari=solari,
            policy=PolicyEngine.from_env(), meter=Meter.from_env(),
            audit=AuditLog.from_env(), quarantine=Quarantine.from_env(solari),
        )
        run = orch.run("Launch a landing page and log the launch in Salesforce")
        run.status            # done | blocked | failed
        run.outcomes          # [TaskOutcome(...), ...]
"""

from __future__ import annotations

from .config import OrchestrationConfig
from .graph import Deps, build_task_graph
from .orchestrator import Orchestrator
from .sink import NullSink, OrchestrationSink
from .state import GoalRun, TaskOutcome, TaskState, TaskStatus

__all__ = [
    "Orchestrator",
    "OrchestrationConfig",
    "OrchestrationSink",
    "NullSink",
    "GoalRun",
    "TaskOutcome",
    "TaskState",
    "TaskStatus",
    "Deps",
    "build_task_graph",
]
