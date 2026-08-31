from django.contrib import admin

from .models import BranchService, Service


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ("service_code", "name", "average_service_time", "is_active")
    search_fields = ("service_code", "name")
    list_filter = ("is_active",)


@admin.register(BranchService)
class BranchServiceAdmin(admin.ModelAdmin):
    list_display = (
        "branch",
        "service",
        "max_bookings_per_slot",
        "is_active",
    )
    list_filter = ("is_active", "branch")
    search_fields = (
        "branch__branch_code",
        "branch__name",
        "service__service_code",
        "service__name",
    )
