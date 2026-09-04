from __future__ import annotations

from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from bench.control_plane.api import views

router = DefaultRouter()
router.register("goals", views.GoalViewSet, basename="goal")
router.register("tasks", views.TaskViewSet, basename="task")
router.register("agents", views.AgentViewSet, basename="agent")
router.register("machines", views.MachineViewSet, basename="machine")
router.register("dispatches", views.DispatchViewSet, basename="dispatch")
router.register("escalations", views.EscalationViewSet, basename="escalation")
router.register("policy/rules", views.PolicyRuleViewSet, basename="policyrule")
router.register("charges", views.ChargeViewSet, basename="charge")

urlpatterns = [
    path("healthz", views.HealthView.as_view()),
    path("live", views.live_view, name="live"),
    path("api/", include(router.urls)),
    path("api/audit", views.AuditView.as_view()),
    path("api/audit/verify", views.AuditVerifyView.as_view()),
    path("api/spend", views.SpendView.as_view()),
    path("api/auth/token", TokenObtainPairView.as_view()),
    path("api/auth/token/refresh", TokenRefreshView.as_view()),
]
