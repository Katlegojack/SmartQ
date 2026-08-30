from django.contrib import admin

from .models import Profile


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    """Internal administration view for Smart Q profile roles and branch scope."""

    list_display = (
        "user",
        "role",
        "branch",
        "gender",
        "disability_status",
        "created_at",
    )
    list_filter = ("role", "branch", "gender", "disability_status")
    search_fields = ("user__username", "user__first_name", "user__last_name", "user__email")
