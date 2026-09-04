"""The control-plane registry: goals, tasks, agents, machines, and the
DB-backed mirrors of the policy / audit / metering records.
"""

from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models


def _uid(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def goal_id() -> str:
    return _uid("goal")


def task_id() -> str:
    return _uid("task")


def agent_id() -> str:
    return _uid("agent")


def dispatch_id() -> str:
    return _uid("disp")


def escalation_id() -> str:
    return _uid("esc")


class Goal(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending"
        PLANNING = "planning"
        RUNNING = "running"
        DONE = "done"
        FAILED = "failed"
        BLOCKED = "blocked"

    id = models.CharField(primary_key=True, max_length=40, default=goal_id, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="goals",
                              on_delete=models.CASCADE, null=True)
    text = models.TextField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    notes = models.TextField(blank=True, default="")
    error = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]


class Task(models.Model):
    class Capability(models.TextChoices):
        SANDBOX = "sandbox"
        BROWSER = "browser"
        DESKTOP = "desktop"

    class Status(models.TextChoices):
        CREATED = "created"
        DISPATCHING = "dispatching"
        DENIED = "denied"
        ESCALATED = "escalated"
        RUNNING = "running"
        QUARANTINE = "quarantine"
        REVIEW = "review"
        DONE = "done"
        REJECTED = "rejected"
        FAILED = "failed"

    id = models.CharField(primary_key=True, max_length=40, default=task_id, editable=False)
    goal = models.ForeignKey(Goal, related_name="tasks", on_delete=models.CASCADE)
    parent = models.ForeignKey("self", null=True, blank=True, related_name="children", on_delete=models.SET_NULL)
    title = models.CharField(max_length=300)
    capability = models.CharField(max_length=16, choices=Capability.choices)
    instructions = models.TextField(blank=True, default="")
    success_criteria = models.JSONField(default=list)
    depends_on = models.JSONField(default=list)          # task ids
    tool = models.CharField(max_length=80, blank=True, null=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.CREATED)
    attempts = models.PositiveIntegerField(default=0)
    result = models.JSONField(null=True, blank=True)
    review = models.JSONField(null=True, blank=True)
    quarantine = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at"]


class Agent(models.Model):
    class Kind(models.TextChoices):
        MANAGEMENT = "management"
        WORKER = "worker"

    class Status(models.TextChoices):
        ACTIVE = "active"
        DISMISSED = "dismissed"

    id = models.CharField(primary_key=True, max_length=40, default=agent_id, editable=False)
    kind = models.CharField(max_length=16, choices=Kind.choices)
    role = models.CharField(max_length=40)               # ceo | engineering | ops | research
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)
    capability = models.CharField(max_length=16, blank=True, null=True)
    task = models.ForeignKey(Task, null=True, blank=True, related_name="agents", on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)
    dismissed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]


class Machine(models.Model):
    class Status(models.TextChoices):
        BOOTING = "booting"
        READY = "ready"
        DESTROYED = "destroyed"
        FAILED = "failed"

    id = models.CharField(primary_key=True, max_length=512)   # the Solari machine id
    kind = models.CharField(max_length=16)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.BOOTING)
    task = models.ForeignKey(Task, null=True, blank=True, related_name="machines", on_delete=models.SET_NULL)
    agent = models.ForeignKey(Agent, null=True, blank=True, related_name="machines", on_delete=models.SET_NULL)
    preview_urls = models.JSONField(default=dict)
    stream_url = models.CharField(max_length=1024, blank=True, null=True)
    recording_id = models.CharField(max_length=256, blank=True, null=True)
    launched_at = models.DateTimeField(auto_now_add=True)
    destroyed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-launched_at"]


class Dispatch(models.Model):
    id = models.CharField(primary_key=True, max_length=40, default=dispatch_id, editable=False)
    task = models.ForeignKey(Task, related_name="dispatches", on_delete=models.CASCADE)
    capability = models.CharField(max_length=16)
    payload = models.JSONField(default=dict)
    effect = models.CharField(max_length=12)             # ALLOW | DENY | ESCALATE (final)
    audit = models.BooleanField(default=False)
    reason = models.TextField(blank=True, default="")
    matched_rules = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class Escalation(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending"
        APPROVED = "approved"
        REJECTED = "rejected"

    id = models.CharField(primary_key=True, max_length=40, default=escalation_id, editable=False)
    task = models.ForeignKey(Task, related_name="escalations", on_delete=models.CASCADE)
    reason = models.TextField(blank=True, default="")
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    resolved_by = models.CharField(max_length=120, blank=True, null=True)
    note = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]


class PolicyRule(models.Model):
    name = models.CharField(primary_key=True, max_length=120)
    match = models.JSONField()
    effect = models.CharField(max_length=12)
    reason = models.TextField(blank=True, null=True)
    enabled = models.BooleanField(default=True)
    priority = models.IntegerField(default=0)            # load order

    class Meta:
        ordering = ["priority", "name"]

    def as_rule_dict(self) -> dict:
        return {"name": self.name, "match": self.match, "effect": self.effect,
                "reason": self.reason, "enabled": self.enabled}


class AuditRow(models.Model):
    """One row per bench.audit event. Mirrors AuditEvent field-for-field."""

    seq = models.BigIntegerField(unique=True)
    event_id = models.CharField(max_length=64)
    ts = models.CharField(max_length=40)
    kind = models.CharField(max_length=64, db_index=True)
    actor = models.CharField(max_length=120, null=True, blank=True)
    task_id = models.CharField(max_length=64, null=True, blank=True, db_index=True)
    dispatch_id = models.CharField(max_length=64, null=True, blank=True)
    worker_id = models.CharField(max_length=64, null=True, blank=True, db_index=True)
    machine_id = models.CharField(max_length=512, null=True, blank=True)
    payload = models.JSONField(default=dict)
    prev_hash = models.CharField(max_length=64)
    hash = models.CharField(max_length=64)

    class Meta:
        ordering = ["seq"]


class Charge(models.Model):
    charge_id = models.CharField(max_length=64, unique=True)
    ts = models.CharField(max_length=40)
    task_id = models.CharField(max_length=64, db_index=True)
    category = models.CharField(max_length=24)
    amount_usd = models.FloatField()
    worker_id = models.CharField(max_length=64, null=True, blank=True)
    machine_id = models.CharField(max_length=512, null=True, blank=True)
    unit = models.CharField(max_length=24, null=True, blank=True)
    quantity = models.FloatField(null=True, blank=True)
    over_budget = models.BooleanField(default=False)
    detail = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
