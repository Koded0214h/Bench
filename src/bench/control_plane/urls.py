from __future__ import annotations

from django.conf import settings
from django.http import FileResponse, Http404, HttpResponseRedirect
from django.urls import include, path, re_path
from django.views.static import serve
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from bench.control_plane.api import views
from bench.control_plane.api.auth import MeView, RegisterView
from bench.control_plane.api.sites import task_site


def spa_index(request, *args, **kwargs):
    index = settings.FRONTEND_DIST / "index.html"
    if not index.exists():
        raise Http404("frontend not built — run: cd frontend && npm install && npm run build")
    resp = FileResponse(open(index, "rb"))
    # The HTML references hashed asset filenames; never let a stale index.html
    # (which would point at a JS bundle that no longer exists) survive a rebuild.
    resp["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return resp


def spa_asset(request, path):
    return serve(request, path, document_root=settings.FRONTEND_DIST / "assets")

router = DefaultRouter()
router.register("companies", views.CompanyViewSet, basename="company")
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
    path("api/status", views.StatusView.as_view()),
    path("live", views.live_view, name="live"),
    path("api/", include(router.urls)),
    path("api/audit", views.AuditView.as_view()),
    path("api/audit/verify", views.AuditVerifyView.as_view()),
    path("api/spend", views.SpendView.as_view()),
    path("api/auth/register", RegisterView.as_view()),
    path("api/auth/token", TokenObtainPairView.as_view()),
    path("api/auth/token/refresh", TokenRefreshView.as_view()),
    path("api/auth/me", MeView.as_view()),
    # a completed sandbox task's captured files, served as a real static site —
    # survives long after the task's own sandbox (and its preview_port URL)
    # has been torn down. Public: same shareability as the sandbox's own link.
    path("sites/<str:task_id>/", task_site, {"path": ""}, name="task-site-index"),
    re_path(r"^sites/(?P<task_id>[^/]+)/(?P<path>.+)$", task_site, name="task-site-asset"),
    # legacy bookmarks
    path("app/", lambda r: HttpResponseRedirect("/")),
    re_path(r"^app/(?P<rest>.*)$", lambda r, rest: HttpResponseRedirect(f"/{rest}")),
    # built React app — owns everything else, including the landing page at "/".
    # Excludes api/healthz/live/admin/sites so a mistyped or slash-less request
    # under those prefixes still 404s (or gets Django's slash-redirect) instead
    # of silently returning the SPA shell.
    re_path(r"^assets/(?P<path>.*)$", spa_asset),
    re_path(r"^(?!api/|healthz|live|admin/|sites/).*$", spa_index),
]
