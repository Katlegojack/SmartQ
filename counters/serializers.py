from rest_framework import serializers

from .models import Counter


class CounterSerializer(serializers.ModelSerializer):
    """Read-only operational counter representation."""

    branch_name = serializers.CharField(source="branch.name", read_only=True)
    assigned_staff_username = serializers.CharField(
        source="assigned_staff.username",
        read_only=True,
        allow_null=True,
    )
    is_staffed = serializers.BooleanField(read_only=True)

    class Meta:
        model = Counter
        fields = [
            "id",
            "branch",
            "branch_name",
            "counter_number",
            "queue_type",
            "status",
            "assigned_staff",
            "assigned_staff_username",
            "is_staffed",
            "created_at",
        ]
        read_only_fields = fields
