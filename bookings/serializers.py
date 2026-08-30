from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone
from rest_framework import serializers

from accounts.models import Profile
from branches.models import Branch
from services.availability import get_branch_service, validate_booking_slot
from services.models import Service
from .models import Booking
from .services import create_guest_walk_in


def raise_slot_validation_error(error_code):
    """Translate availability-engine outcomes into DRF validation errors."""
    messages = {
        "service_not_offered": "The selected service is not offered at this branch.",
        "past_date": "Booking date cannot be in the past.",
        "invalid_slot": "Select one of the available appointment time slots.",
        "past_slot": "This appointment slot has already passed.",
        "slot_full": "This appointment slot is fully booked.",
    }
    message = messages.get(error_code)
    if message:
        raise serializers.ValidationError({"booking_time": message})


class BookingCreateSerializer(serializers.ModelSerializer):
    """Validate a customer-created online appointment against branch capacity."""

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
            "source",
            "checked_in_at",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "status",
            "source",
            "checked_in_at",
            "created_at",
        ]

    def validate_booking_date(self, value):
        if value < timezone.localdate():
            raise serializers.ValidationError("Booking date cannot be in the past.")
        return value

    def validate(self, attrs):
        attrs = super().validate(attrs)
        branch = attrs.get("branch")
        service = attrs.get("service")
        booking_date = attrs.get("booking_date")
        booking_time = attrs.get("booking_time")

        if branch and service and booking_date and booking_time:
            _, error_code = validate_booking_slot(
                branch,
                service,
                booking_date,
                booking_time,
            )
            raise_slot_validation_error(error_code)

        return attrs


class BookingListSerializer(serializers.ModelSerializer):
    """Read-only booking representation for customer and staff workflows."""

    branch_name = serializers.CharField(source="branch.name", read_only=True)
    service_name = serializers.CharField(source="service.name", read_only=True)
    is_checked_in = serializers.BooleanField(read_only=True)
    customer_name = serializers.CharField(source="customer_display_name", read_only=True)
    queue_ticket = serializers.SerializerMethodField()

    class Meta:
        model = Booking
        fields = [
            "id",
            "customer_name",
            "source",
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
    """Validate a new appointment slot against the existing branch/service."""

    class Meta:
        model = Booking
        fields = ["booking_date", "booking_time"]

    def validate_booking_date(self, value):
        if value < timezone.localdate():
            raise serializers.ValidationError("Booking date cannot be in the past.")
        return value

    def validate(self, attrs):
        attrs = super().validate(attrs)
        booking = self.instance
        if booking is None:
            return attrs

        booking_date = attrs.get("booking_date", booking.booking_date)
        booking_time = attrs.get("booking_time", booking.booking_time)

        _, error_code = validate_booking_slot(
            booking.branch,
            booking.service,
            booking_date,
            booking_time,
            exclude_booking=booking,
        )
        raise_slot_validation_error(error_code)
        return attrs


class GuestWalkInSerializer(serializers.Serializer):
    """Reception input for a guest who does not have a Smart Q account."""

    full_name = serializers.CharField(max_length=150)
    phone_number = serializers.CharField(max_length=30, required=False, allow_blank=True)
    date_of_birth = serializers.DateField()
    gender = serializers.ChoiceField(choices=Profile.GENDER_CHOICE)
    disability_status = serializers.BooleanField(required=False, default=False)
    is_pregnant = serializers.BooleanField(required=False, default=False)
    service = serializers.PrimaryKeyRelatedField(
        queryset=Service.objects.filter(is_active=True)
    )

    def validate_date_of_birth(self, value):
        if value > timezone.localdate():
            raise serializers.ValidationError("Date of birth cannot be in the future.")
        return value

    def validate(self, attrs):
        attrs = super().validate(attrs)

        if attrs.get("is_pregnant") and attrs.get("gender") != Profile.FEMALE:
            raise serializers.ValidationError(
                {"is_pregnant": "Pregnancy priority applies only to a female profile."}
            )

        branch = self.context["branch"]
        if get_branch_service(branch, attrs["service"]) is None:
            raise serializers.ValidationError(
                {"service": "This service is not offered at the selected branch."}
            )

        return attrs

    def create(self, validated_data):
        branch = self.context["branch"]
        return create_guest_walk_in(
            branch=branch,
            service=validated_data["service"],
            full_name=validated_data["full_name"],
            phone_number=validated_data.get("phone_number", ""),
            date_of_birth=validated_data["date_of_birth"],
            gender=validated_data["gender"],
            disability_status=validated_data.get("disability_status", False),
            is_pregnant=validated_data.get("is_pregnant", False),
        )
