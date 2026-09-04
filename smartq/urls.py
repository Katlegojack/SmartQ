"""
URL configuration for Smart Q.

API routes are grouped by Django app so each domain owns its own endpoint paths.
Frontend routes remain thin Django template entry points; authentication, role and
branch authority continue to come from the existing API contract.
"""

from django.contrib import admin
from django.urls import include, path
from django.views.generic import TemplateView


APP_TEMPLATE = "frontend/app_shell.html"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("queues.urls")),
    path("api/v1/accounts/", include("accounts.api_urls")),
    path("api/v1/notifications/", include("notifications.api_urls")),
    path("api/v1/services/", include("services.api_urls")),
    path("api/v1/branches/", include("branches.api_urls")),
    path("api/v1/bookings/", include("bookings.api_urls")),
    path("api/v1/queues/", include("queues.api_urls")),
    path("api/v1/counters/", include("counters.api_urls")),
    path("api/v1/rescheduling/", include("rescheduling.api_urls")),
    path("api/v1/dashboard/", include("dashboard.api_urls")),

    path("login/", TemplateView.as_view(template_name="frontend/login.html"), name="frontend_login"),
    path(
        "staff-login/",
        TemplateView.as_view(
            template_name="frontend/login.html",
            extra_context={"staff_access": True},
        ),
        name="frontend_staff_login",
    ),
    path("register/", TemplateView.as_view(template_name="frontend/register.html"), name="frontend_register"),

    path(
        "app/",
        TemplateView.as_view(
            template_name=APP_TEMPLATE,
            extra_context={"workspace_title": "Smart Q workspace", "workspace_role": ""},
        ),
        name="frontend_app",
    ),
    path(
        "app/customer/",
        TemplateView.as_view(template_name="frontend/customer_dashboard.html"),
        name="frontend_customer_workspace",
    ),
    path(
        "app/reception/",
        TemplateView.as_view(template_name="frontend/reception_workspace.html"),
        name="frontend_reception_workspace",
    ),
    path(
        "app/counter/",
        TemplateView.as_view(template_name="frontend/counter_workspace.html"),
        name="frontend_counter_workspace",
    ),
    path(
        "app/manager/",
        TemplateView.as_view(template_name="frontend/manager_workspace.html"),
        name="frontend_manager_workspace",
    ),
    path(
        "app/admin/",
        TemplateView.as_view(template_name="frontend/admin_workspace.html"),
        name="frontend_admin_workspace",
    ),
    path(
        "app/history/",
        TemplateView.as_view(template_name="frontend/history_reporting_workspace.html"),
        name="frontend_history_reporting_workspace",
    ),
    path(
        "app/recovery/",
        TemplateView.as_view(template_name="frontend/customer_recovery_workspace.html"),
        name="frontend_customer_recovery_workspace",
    ),
    path("", TemplateView.as_view(template_name="frontend/index.html"), name="frontend_home"),
]
