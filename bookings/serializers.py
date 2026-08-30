from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone
from rest_framework import serializers

from branches.models import Branch
from services.models import Service
from .models import Booking


class BookingCreateSerializer(serializers.ModelSerializer):
    """Validate customer input when a new booking is created."""

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
            "checked_in_at",
            "created_at",
        ]
        read_only_fields = ["id", "status", "checked_in_at", "created_at"]

    def validate_booking_date(self, value):
        if value < timezone.localdate():
            raise serializers.ValidationError("Booking date cannot be in the past.")
        return value

    def validate(self, attrs):
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
    """Read-only booking representation including live check-in state."""

    branch_name = serializers.CharField(source="branch.name", read_only=True)
    service_name = serializers.CharField(source="service.name", read_only=True)
    is_checked_in = serializers.BooleanField(read_only=True)
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
            "checked_in_at",
            "is_checked_in",
            "created_at",
            "queue_ticket",
        ]
        read_only_fields = fields

    def get_queue_ticket(self, obj):
        try:
            ticket = obj.queueticket
        except ObjectDoesNotExist:
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
