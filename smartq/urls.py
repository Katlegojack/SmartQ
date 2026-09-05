"""
URL configuration for Smart Q.

Django + Django REST Framework remain Smart Q's backend and authority. Day 53
moves the browser runtime to a single React + TypeScript application while
preserving the existing public URLs and named routes during the migration.
"""

from django.contrib import admin
from django.urls import include, path
from django.views.generic import TemplateView


REACT_TEMPLATE = "frontend/react_app.html"


def react_entry(page_kind, *, expected_role=""):
    return TemplateView.as_view(
        template_name=REACT_TEMPLATE,
        extra_context={
            "page_kind": page_kind,
            "expected_role": expected_role,
        },
    )


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

    path("login/", react_entry("login"), name="frontend_login"),
    path("staff-login/", react_entry("staff_login"), name="frontend_staff_login"),
    path("register/", react_entry("register"), name="frontend_register"),

    path("app/", react_entry("router"), name="frontend_app"),
    path(
        "app/customer/",
        react_entry("customer", expected_role="customer"),
        name="frontend_customer_workspace",
    ),
    path(
        "app/reception/",
        react_entry("reception", expected_role="receptionist"),
        name="frontend_reception_workspace",
    ),
    path(
        "app/counter/",
        react_entry("counter", expected_role="counter_staff"),
        name="frontend_counter_workspace",
    ),
    path(
        "app/manager/",
        react_entry("manager", expected_role="branch_manager"),
        name="frontend_manager_workspace",
    ),
    path(
        "app/admin/",
        react_entry("admin", expected_role="system_admin"),
        name="frontend_admin_workspace",
    ),
    path("app/history/", react_entry("history"), name="frontend_history_reporting_workspace"),
    path("app/recovery/", react_entry("recovery"), name="frontend_customer_recovery_workspace"),
    path("", react_entry("home"), name="frontend_home"),
]
