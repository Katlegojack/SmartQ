from django.apps import AppConfig


class DashboardConfig(AppConfig):
    """Configuration for Smart Q's read-only manager dashboard domain."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "dashboard"
