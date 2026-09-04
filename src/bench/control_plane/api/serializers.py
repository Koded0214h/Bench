from __future__ import annotations

from rest_framework import serializers

from .models import Agent, Charge, Dispatch, Escalation, Goal, Machine, PolicyRule, Task


class TaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = Task
        fields = [
            "id", "goal_id", "parent_id", "title", "capability", "instructions",
            "success_criteria", "depends_on", "tool", "status", "attempts",
            "result", "review", "quarantine", "created_at", "updated_at",
        ]
        read_only_fields = fields


class GoalSerializer(serializers.ModelSerializer):
    tasks = TaskSerializer(many=True, read_only=True)
    owner = serializers.CharField(source="owner.username", read_only=True, default=None)

    class Meta:
        model = Goal
        fields = ["id", "owner", "text", "status", "notes", "error", "created_at", "updated_at", "tasks"]
        read_only_fields = fields


class GoalCreateSerializer(serializers.Serializer):
    text = serializers.CharField()
    run = serializers.BooleanField(required=False, default=None, allow_null=True)


class AgentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Agent
        fields = ["id", "kind", "role", "status", "capability", "task_id", "created_at", "dismissed_at"]
        read_only_fields = fields


class MachineSerializer(serializers.ModelSerializer):
    class Meta:
        model = Machine
        fields = [
            "id", "kind", "status", "task_id", "agent_id", "preview_urls",
            "stream_url", "recording_id", "launched_at", "destroyed_at",
        ]
        read_only_fields = fields


class DispatchSerializer(serializers.ModelSerializer):
    class Meta:
        model = Dispatch
        fields = ["id", "task_id", "capability", "payload", "effect", "audit",
                  "reason", "matched_rules", "created_at"]
        read_only_fields = fields


class EscalationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Escalation
        fields = ["id", "task_id", "reason", "status", "resolved_by", "note",
                  "created_at", "resolved_at"]
        read_only_fields = ["id", "task_id", "reason", "status", "created_at", "resolved_at"]


class EscalationResolveSerializer(serializers.Serializer):
    approved = serializers.BooleanField()
    resolved_by = serializers.CharField(required=False, allow_blank=True, default="")
    note = serializers.CharField(required=False, allow_blank=True, default="")


class PolicyRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = PolicyRule
        fields = ["name", "match", "effect", "reason", "enabled", "priority"]
        read_only_fields = fields


class ChargeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Charge
        fields = ["charge_id", "ts", "task_id", "category", "amount_usd", "worker_id",
                  "machine_id", "unit", "quantity", "over_budget", "detail"]
        read_only_fields = fields
