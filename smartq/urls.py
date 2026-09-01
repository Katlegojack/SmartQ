"""
URL configuration for Smart Q.

API routes are grouped by Django app so each domain owns its own endpoint paths.
"""

from django.contrib import admin
from django.urls import include, path
from django.views.generic import TemplateView


urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("queues.urls")),

    # Authentication and current-account endpoints.
    path("api/v1/accounts/", include("accounts.api_urls")),

    # Domain APIs.
    path("api/v1/notifications/", include("notifications.api_urls")),
    path("api/v1/services/", include("services.api_urls")),
    path("api/v1/branches/", include("branches.api_urls")),
    path("api/v1/bookings/", include("bookings.api_urls")),
    path("api/v1/queues/", include("queues.api_urls")),
    path("api/v1/counters/", include("counters.api_urls")),
    path("api/v1/rescheduling/", include("rescheduling.api_urls")),

    # Day 34 manager read-model APIs.
    path("api/v1/dashboard/", include("dashboard.api_urls")),

    # Frontend foundation. Role-aware screens are added from Day 42 onward.
    path(
        "",
        TemplateView.as_view(template_name="frontend/index.html"),
        name="frontend_home",
    ),
]
