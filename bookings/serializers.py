from django.utils import timezone
from rest_framework import serializers

from branches.models import Branch
from services.models import Service
from .models import Booking


class BookingCreateSerializer(serializers.ModelSerializer):
    """Validate customer input when a new booking is created."""

    # Customers may only choose active catalogue records.
    branch = serializers.PrimaryKeyRelatedField(
        queryset=Branch.objects.filter(is_active=True)
    )
    service = serializers.PrimaryKeyRelatedField(
        queryset=Service.objects.filter(is_active=True)
    )

    class Meta:
        model = Booking
        fields = [
            "id",
            "branch",
            "service",
            "booking_date",
            "booking_time",
            "is_pregnant",
            "status",
            "created_at",
        ]
        read_only_fields = ["id", "status", "created_at"]

    def validate_booking_date(self, value):
        """Prevent customers from creating bookings in the past."""
        if value < timezone.localdate():
            raise serializers.ValidationError("Booking date cannot be in the past.")
        return value

    def validate(self, attrs):
        """Keep booking times inside the selected branch's operating hours."""
        attrs = super().validate(attrs)
        branch = attrs.get("branch")
        booking_time = attrs.get("booking_time")

        if branch and booking_time:
            if booking_time < branch.opening_time or booking_time > branch.closing_time:
                raise serializers.ValidationError(
                    {
                        "booking_time": (
                            "Booking time must be within the selected branch's operating hours."
                        )
                    }
                )

        return attrs


class BookingListSerializer(serializers.ModelSerializer):
    """Read-only customer booking representation."""

    branch_name = serializers.CharField(source="branch.name", read_only=True)
    service_name = serializers.CharField(source="service.name", read_only=True)
    queue_ticket = serializers.SerializerMethodField()

    class Meta:
        model = Booking
        fields = [
            "id",
            "branch",
            "branch_name",
            "service",
            "service_name",
            "booking_date",
            "booking_time",
            "is_pregnant",
            "status",
            "created_at",
            "queue_ticket",
        ]
        read_only_fields = fields

    def get_queue_ticket(self, obj):
        # A missing reverse OneToOne relationship should return null instead of
        # hiding unrelated programming errors with a broad `except Exception`.
        try:
            ticket = obj.queueticket
        except Booking.queueticket.RelatedObjectDoesNotExist:
            return None

        return {
            "id": ticket.id,
            "queue_number": ticket.queue_number,
            "queue_type": ticket.queue_type,
            "status": ticket.status,
        }


class BookingRescheduleSerializer(serializers.ModelSerializer):
    """Allow customers to change only the date and time of a booking."""

    class Meta:
        model = Booking
        fields = ["booking_date", "booking_time"]

    def validate_booking_date(self, value):
        if value < timezone.localdate():
            raise serializers.ValidationError("Booking date cannot be in the past.")
        return value

    def validate(self, attrs):
        attrs = super().validate(attrs)

        # During PATCH requests, unchanged values come from the current booking.
        branch = self.instance.branch if self.instance else None
        booking_time = attrs.get(
            "booking_time",
            self.instance.booking_time if self.instance else None,
        )

        if branch and booking_time:
            if booking_time < branch.opening_time or booking_time > branch.closing_time:
                raise serializers.ValidationError(
                    {
                        "booking_time": (
                            "Booking time must be within the branch's operating hours."
                        )
                    }
                )

        return attrs
