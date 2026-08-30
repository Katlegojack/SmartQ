"""
URL configuration for Smart Q.

API routes are grouped by Django app so each domain owns its own endpoint paths.
"""

from django.contrib import admin
from django.urls import include, path


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
]
