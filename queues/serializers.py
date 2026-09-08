from rest_framework import serializers

from .models import QueueTicket


class QueueTicketSerializer(serializers.ModelSerializer):
    """Read-only queue ticket representation for customer and staff screens."""

    booking_id = serializers.IntegerField(source="booking.id", read_only=True)
    branch_name = serializers.CharField(source="booking.branch.name", read_only=True)
    service_name = serializers.CharField(source="booking.service.name", read_only=True)
    booking_date = serializers.DateField(source="booking.booking_date", read_only=True)
    booking_time = serializers.TimeField(source="booking.booking_time", read_only=True)
    checked_in_at = serializers.DateTimeField(source="booking.checked_in_at", read_only=True)
    customer_name = serializers.CharField(
        source="booking.customer_display_name",
        read_only=True,
    )
    assigned_counter_number = serializers.CharField(
        source="assigned_counter.counter_number",
        read_only=True,
        allow_null=True,
    )

    class Meta:
        model = QueueTicket
        fields = [
            "id",
            "booking_id",
            "queue_number",
            "queue_type",
            "status",
            "assigned_counter",
            "assigned_counter_number",
            "branch_name",
            "service_name",
            "booking_date",
            "booking_time",
            "checked_in_at",
            "customer_name",
            "service_started_at",
            "service_completed_at",
            "service_target_seconds",
            "actual_service_seconds",
            "service_variance_seconds",
            "created_at",
        ]
        read_only_fields = fields
