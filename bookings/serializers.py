from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone
from rest_framework import serializers

from accounts.models import Profile
from branches.models import Branch
from services.models import Service
from .models import Booking
from .services import create_guest_walk_in


class BookingCreateSerializer(serializers.ModelSerializer):
    """Validate customer input when a new online booking is created."""

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
    """Allow registered customers to change only date/time of an online booking."""

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
