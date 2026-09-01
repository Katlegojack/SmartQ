from rest_framework import serializers

from branches.models import Branch

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


class ServiceAdminSerializer(serializers.ModelSerializer):
    """System Admin serializer for global service catalogue management."""

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
        read_only_fields = ["id", "created_at"]

    def validate_average_service_time(self, value):
        if value <= 0:
            raise serializers.ValidationError(
                "Average service time must be greater than zero minutes."
            )
        return value


class BranchServiceAdminSerializer(serializers.ModelSerializer):
    """System Admin serializer for branch/service capacity configuration."""

    branch = serializers.PrimaryKeyRelatedField(queryset=Branch.objects.all())
    service = serializers.PrimaryKeyRelatedField(queryset=Service.objects.all())
    branch_name = serializers.CharField(source="branch.name", read_only=True)
    service_name = serializers.CharField(source="service.name", read_only=True)

    class Meta:
        model = BranchService
        fields = [
            "id",
            "branch",
            "branch_name",
            "service",
            "service_name",
            "max_bookings_per_slot",
            "is_active",
            "created_at",
        ]
        read_only_fields = ["id", "branch_name", "service_name", "created_at"]

    def validate(self, attrs):
        branch = attrs.get("branch", getattr(self.instance, "branch", None))
        service = attrs.get("service", getattr(self.instance, "service", None))
        is_active = attrs.get(
            "is_active",
            getattr(self.instance, "is_active", True),
        )

        if is_active and branch is not None and not branch.is_active:
            raise serializers.ValidationError(
                {"branch": "An active mapping requires an active branch."}
            )

        if is_active and service is not None and not service.is_active:
            raise serializers.ValidationError(
                {"service": "An active mapping requires an active service."}
            )

        return attrs
