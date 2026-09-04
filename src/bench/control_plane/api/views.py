from __future__ import annotations

from django.shortcuts import render
from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from bench.audit import AuditLog

from .models import Agent, Charge, Dispatch, Escalation, Goal, Machine, PolicyRule, Task
from .serializers import (
    AgentSerializer,
    ChargeSerializer,
    DispatchSerializer,
    EscalationResolveSerializer,
    EscalationSerializer,
    GoalCreateSerializer,
    GoalSerializer,
    MachineSerializer,
    PolicyRuleSerializer,
    TaskSerializer,
)
from .stores import DjangoAuditStore


# --------------------------------------------------------------------------
# ownership helpers
# --------------------------------------------------------------------------

def _owned_goal_ids(user) -> list[str]:
    return list(Goal.objects.filter(owner=user).values_list("id", flat=True))


def _owned_task_ids(user) -> set[str]:
    ids = set(Task.objects.filter(goal__owner=user).values_list("id", flat=True))
    ids.update(_owned_goal_ids(user))          # audit uses the goal id as the root task id
    return ids


# --------------------------------------------------------------------------

class GoalViewSet(mixins.CreateModelMixin, mixins.ListModelMixin,
                  mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = GoalSerializer

    def get_queryset(self):
        return Goal.objects.filter(owner=self.request.user).prefetch_related("tasks")

    def create(self, request, *args, **kwargs):
        payload = GoalCreateSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        goal = Goal.objects.create(text=payload.validated_data["text"], owner=request.user)

        from django.conf import settings

        want_run = payload.validated_data.get("run")
        if want_run is None:
            want_run = bool(getattr(settings, "BENCH_AUTORUN", False))
        if want_run:
            from bench.control_plane.runner import run_goal_in_thread

            run_goal_in_thread(goal.id)
            goal.refresh_from_db()

        return Response(GoalSerializer(goal).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def run(self, request, pk=None):
        goal = self.get_object()
        if goal.status in (Goal.Status.RUNNING, Goal.Status.PLANNING):
            return Response({"detail": "already running"}, status=409)
        from bench.control_plane.runner import run_goal_in_thread

        run_goal_in_thread(goal.id)
        goal.refresh_from_db()
        return Response(GoalSerializer(goal).data, status=202)


class TaskViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = TaskSerializer

    def get_queryset(self):
        qs = Task.objects.filter(goal__owner=self.request.user)
        goal = self.request.query_params.get("goal")
        state = self.request.query_params.get("status")
        if goal:
            qs = qs.filter(goal_id=goal)
        if state:
            qs = qs.filter(status=state)
        return qs


class AgentViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = AgentSerializer

    def get_queryset(self):
        qs = Agent.objects.filter(task__goal__owner=self.request.user)
        if self.request.query_params.get("active") in ("1", "true"):
            qs = qs.filter(status=Agent.Status.ACTIVE)
        return qs


class MachineViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = MachineSerializer

    def get_queryset(self):
        qs = Machine.objects.filter(task__goal__owner=self.request.user)
        if self.request.query_params.get("live") in ("1", "true"):
            qs = qs.exclude(status=Machine.Status.DESTROYED)
        return qs


class DispatchViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = DispatchSerializer

    def get_queryset(self):
        qs = Dispatch.objects.filter(task__goal__owner=self.request.user)
        task = self.request.query_params.get("task")
        return qs.filter(task_id=task) if task else qs


class EscalationViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = EscalationSerializer

    def get_queryset(self):
        qs = Escalation.objects.filter(task__goal__owner=self.request.user)
        if self.request.query_params.get("pending") in ("1", "true"):
            qs = qs.filter(status=Escalation.Status.PENDING)
        return qs

    @action(detail=True, methods=["post"])
    def resolve(self, request, pk=None):
        esc = self.get_object()
        if esc.status != Escalation.Status.PENDING:
            return Response({"detail": f"already {esc.status}"}, status=409)
        body = EscalationResolveSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        approved = body.validated_data["approved"]
        esc.status = Escalation.Status.APPROVED if approved else Escalation.Status.REJECTED
        esc.resolved_by = body.validated_data.get("resolved_by") or request.user.username
        esc.note = body.validated_data.get("note", "")
        esc.resolved_at = timezone.now()
        esc.save()

        if approved:
            from bench.control_plane.runner import resume_in_thread

            resume_in_thread(esc.id)
        else:
            Task.objects.filter(pk=esc.task_id).update(status=Task.Status.REJECTED)
        return Response(EscalationSerializer(esc).data)


class PolicyRuleViewSet(viewsets.ReadOnlyModelViewSet):
    """Company-wide rules — readable by any authenticated user."""

    queryset = PolicyRule.objects.all()
    serializer_class = PolicyRuleSerializer


class ChargeViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ChargeSerializer

    def get_queryset(self):
        qs = Charge.objects.filter(task_id__in=_owned_task_ids(self.request.user))
        task = self.request.query_params.get("task")
        return qs.filter(task_id=task) if task else qs


class AuditView(APIView):
    def get(self, request):
        owned = _owned_task_ids(request.user)
        log = AuditLog(DjangoAuditStore())
        task = request.query_params.get("task")
        if task and task not in owned:
            return Response({"count": 0, "events": []})
        events = [
            e for e in log.events(
                task_id=task,
                worker_id=request.query_params.get("worker"),
                kinds=request.query_params.getlist("kind") or None,
            )
            if e.task_id in owned or e.worker_id in owned
        ]
        limit = int(request.query_params.get("limit", 200))
        return Response({"count": len(events), "events": [e.to_dict() for e in events[:limit]]})


class AuditVerifyView(APIView):
    def get(self, request):
        # chain integrity is global; any authed user may check it
        result = AuditLog(DjangoAuditStore()).verify()
        return Response({"ok": result.ok, "checked": result.checked,
                         "broken_at": result.broken_at, "reason": result.reason})


class SpendView(APIView):
    def get(self, request):
        owned = _owned_task_ids(request.user)
        rows = Charge.objects.filter(task_id__in=owned)
        task = request.query_params.get("task")
        if task:
            rows = rows.filter(task_id=task)
        by_task: dict[str, dict] = {}
        for c in rows:
            b = by_task.setdefault(c.task_id, {"total_usd": 0.0, "by_category": {}, "charges": 0})
            b["total_usd"] = round(b["total_usd"] + c.amount_usd, 8)
            b["by_category"][c.category] = round(b["by_category"].get(c.category, 0.0) + c.amount_usd, 8)
            b["charges"] += 1
        grand = round(sum(b["total_usd"] for b in by_task.values()), 6)
        return Response({"total_usd": grand, "tasks": by_task})


class HealthView(APIView):
    authentication_classes: list = []
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({"status": "ok"})


def live_view(request):
    return render(request, "live.html", {})
