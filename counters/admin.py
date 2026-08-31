from django.contrib import admin

from .models import Counter


@admin.register(Counter)
class CounterAdmin(admin.ModelAdmin):
    """Operational admin view for counter state and current assignment."""

    list_display = [
        "counter_number",
        "branch",
        "queue_type",
        "status",
        "assigned_staff",
    ]
    list_filter = ["branch", "queue_type", "status"]
    search_fields = [
        "counter_number",
        "branch__name",
        "assigned_staff__username",
    ]
