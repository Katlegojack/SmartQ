from rest_framework import serializers

from .models import QueueTicket


class QueueTicketSerializer(serializers.ModelSerializer):
    """
    Read-only representation of a queue ticket for customer and staff screens.

    Related booking information is exposed here so the frontend does not need
    extra API calls just to display the branch, service, booking time, or the
    customer being served.
    """

    booking_id = serializers.IntegerField(source="booking.id", read_only=True)
    branch_name = serializers.CharField(source="booking.branch.name", read_only=True)
    service_name = serializers.CharField(source="booking.service.name", read_only=True)
    booking_date = serializers.DateField(source="booking.booking_date", read_only=True)
    booking_time = serializers.TimeField(source="booking.booking_time", read_only=True)
    customer_name = serializers.SerializerMethodField()

    class Meta:
        model = QueueTicket
        fields = [
            "id",
            "booking_id",
            "queue_number",
            "queue_type",
            "status",
            "assigned_counter",
            "branch_name",
            "service_name",
            "booking_date",
            "booking_time",
            "customer_name",
            "created_at",
        ]
        read_only_fields = fields

    def get_customer_name(self, obj):
        """Prefer the customer's full name, but safely fall back to username."""
        user = obj.booking.user
        full_name = user.get_full_name().strip()
        return full_name or user.username
