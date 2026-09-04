from __future__ import annotations

from django.conf import settings
from django.http import FileResponse, Http404, HttpResponseRedirect
from django.urls import include, path, re_path
from django.views.static import serve
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from bench.control_plane.api import views
from bench.control_plane.api.auth import MeView, RegisterView


def spa_index(request, *args, **kwargs):
    index = settings.FRONTEND_DIST / "index.html"
    if not index.exists():
        raise Http404("frontend not built — run: cd frontend && npm install && npm run build")
    return FileResponse(open(index, "rb"))


def spa_asset(request, path):
    return serve(request, path, document_root=settings.FRONTEND_DIST / "assets")

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
    path("api/auth/register", RegisterView.as_view()),
    path("api/auth/token", TokenObtainPairView.as_view()),
    path("api/auth/token/refresh", TokenRefreshView.as_view()),
    path("api/auth/me", MeView.as_view()),
    # built React app
    re_path(r"^app/assets/(?P<path>.*)$", spa_asset),
    re_path(r"^app/.*$", spa_index),
    path("", lambda r: HttpResponseRedirect("/app/")),
]
