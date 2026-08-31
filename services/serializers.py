from rest_framework import serializers

from .models import BranchService, Service


class ServiceSerializer(serializers.ModelSerializer):
    """Public read-only service catalogue representation."""

    class Meta:
        model = Service
        fields = [
            "id",
            "service_code",
            "name",
            "description",
            "average_service_time",
            "is_active",
            "created_at",
        ]
        read_only_fields = fields


class BranchServiceSerializer(serializers.ModelSerializer):
    """Public branch-specific service offering and appointment capacity."""

    service_id = serializers.IntegerField(source="service.id", read_only=True)
    service_code = serializers.CharField(source="service.service_code", read_only=True)
    service_name = serializers.CharField(source="service.name", read_only=True)
    description = serializers.CharField(source="service.description", read_only=True)
    average_service_time = serializers.IntegerField(
        source="service.average_service_time",
        read_only=True,
    )

    class Meta:
        model = BranchService
        fields = [
            "id",
            "branch",
            "service_id",
            "service_code",
            "service_name",
            "description",
            "average_service_time",
            "max_bookings_per_slot",
            "is_active",
        ]
        read_only_fields = fields
