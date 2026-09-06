"""
URL configuration for Smart Q.

Django + Django REST Framework remain Smart Q's backend and authority. The
React + TypeScript runtime is used for authenticated role workspaces, while the
approved Smart Q landing, registration and role-selection sign-in screens stay
on their established Django templates.
"""

import os
import time

from django.contrib import admin
from django.urls import include, path
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.views.generic import TemplateView


REACT_TEMPLATE = "frontend/react_app.html"
FRONTEND_ASSET_VERSION = os.getenv("SMARTQ_FRONTEND_ASSET_VERSION") or str(time.time_ns())


@method_decorator(never_cache, name="dispatch")
class FrontendTemplateView(TemplateView):
    """Never cache Smart Q entry shells that point at mutable frontend assets."""


def frontend_page(template_name, **extra_context):
    context = {"frontend_asset_version": FRONTEND_ASSET_VERSION, **extra_context}
    return FrontendTemplateView.as_view(
        template_name=template_name,
        extra_context=context,
    )


def react_entry(page_kind, *, expected_role=""):
    return frontend_page(
        REACT_TEMPLATE,
        page_kind=page_kind,
        expected_role=expected_role,
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

    path(
        "login/",
        frontend_page(
            "frontend/login.html",
            initial_role="customer",
        ),
        name="frontend_login",
    ),
    path(
        "staff-login/",
        frontend_page(
            "frontend/login.html",
            initial_role="receptionist",
        ),
        name="frontend_staff_login",
    ),
    path(
        "register/",
        frontend_page("frontend/register.html"),
        name="frontend_register",
    ),

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
    path(
        "app/admin/counters/",
        react_entry("admin_counters", expected_role="system_admin"),
        name="frontend_admin_counter_workspace",
    ),
    path("app/history/", react_entry("history"), name="frontend_history_reporting_workspace"),
    path("app/recovery/", react_entry("recovery"), name="frontend_customer_recovery_workspace"),
    path(
        "",
        frontend_page("frontend/index.html"),
        name="frontend_home",
    ),
]
