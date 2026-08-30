from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.generics import CreateAPIView, ListAPIView, RetrieveAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsQueueViewer
from queues.models import QueueTicket
from queues.services import (
    check_in_booking,
    create_queue_ticket_for_booking,
    determine_queue_type,
    generate_queue_number,
    get_check_in_opens_at,
)
from .models import Booking
from .serializers import (
    BookingCreateSerializer,
    BookingListSerializer,
    BookingRescheduleSerializer,
)


def check_in_error_response(error_code, booking=None):
    """Translate reusable check-in service outcomes into clear HTTP responses."""
    if error_code == "too_early":
        opens_at = get_check_in_opens_at(booking) if booking is not None else None
        return Response(
            {
                "detail": "Check-in is not open yet. It opens six hours before your appointment.",
                "check_in_opens_at": opens_at,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )
    if error_code == "wrong_date":
        return Response(
            {"detail": "This booking can no longer enter the current live queue."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if error_code == "final_state":
        return Response(
            {"detail": "Cancelled, completed, or no-show bookings cannot be checked in."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if error_code == "already_checked_in":
        return Response(
            {"detail": "This booking is already checked in and is part of the live queue."},
            status=status.HTTP_409_CONFLICT,
        )
    return None


class BookingCreateAPIView(CreateAPIView):
    """Create a scheduled booking and its non-live queue ticket."""

    serializer_class = BookingCreateSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        with transaction.atomic():
            booking = serializer.save(user=self.request.user)
            if not QueueTicket.objects.filter(booking=booking).exists():
                create_queue_ticket_for_booking(booking)


class MyBookingListAPIView(ListAPIView):
    serializer_class = BookingListSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Booking.objects.filter(user=self.request.user).select_related(
            "branch", "service"
        ).order_by("-created_at")


class BookingDetailAPIView(RetrieveAPIView):
    serializer_class = BookingListSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Booking.objects.filter(user=self.request.user).select_related(
            "branch", "service"
        )


class BookingCheckInAPIView(APIView):
    """Allow a customer to activate their own booking into the live queue."""

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        booking = get_object_or_404(Booking, pk=pk, user=request.user)
        ticket, error_code = check_in_booking(booking)

        error_response = check_in_error_response(error_code, booking=booking)
        if error_response:
            return error_response

        booking.refresh_from_db()
        return Response(
            BookingListSerializer(booking).data,
            status=status.HTTP_200_OK,
        )


class StaffBookingCheckInAPIView(APIView):
    """Allow authorised branch staff to activate a customer's live queue ticket."""

    permission_classes = [IsQueueViewer]

    def post(self, request, pk):
        booking = get_object_or_404(
            Booking.objects.select_related("branch", "service", "user"),
            pk=pk,
        )
        self.check_object_permissions(request, booking)

        ticket, error_code = check_in_booking(booking)
        error_response = check_in_error_response(error_code, booking=booking)
        if error_response:
            return error_response

        booking.refresh_from_db()
        return Response(
            BookingListSerializer(booking).data,
            status=status.HTTP_200_OK,
        )


class BookingCancelAPIView(APIView):
    """Cancel an eligible booking and its connected queue ticket together."""

    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def patch(self, request, pk):
        booking = get_object_or_404(Booking, pk=pk, user=request.user)

        if booking.status == Booking.COMPLETED:
            return Response(
                {"detail": "Completed bookings cannot be cancelled."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if booking.status == Booking.NO_SHOW:
            return Response(
                {"detail": "No-show bookings cannot be cancelled."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if booking.status == Booking.CANCELLED:
            return Response(
                BookingListSerializer(booking).data,
                status=status.HTTP_200_OK,
            )

        booking.status = Booking.CANCELLED
        booking.save(update_fields=["status"])

        try:
            ticket = booking.queueticket
        except QueueTicket.DoesNotExist:
            ticket = None

        if ticket:
            ticket.status = QueueTicket.CANCELLED
            ticket.assigned_counter = None
            ticket.save(update_fields=["status", "assigned_counter"])

        return Response(
            BookingListSerializer(booking).data,
            status=status.HTTP_200_OK,
        )


class BookingRescheduleAPIView(APIView):
    """Move a booking to a new date/time and require a fresh future check-in."""

    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def patch(self, request, pk):
        booking = get_object_or_404(Booking, pk=pk, user=request.user)

        if booking.status == Booking.COMPLETED:
            return Response(
                {"detail": "Completed bookings cannot be rescheduled."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if booking.status == Booking.CANCELLED:
            return Response(
                {"detail": "Cancelled bookings cannot be rescheduled."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if booking.status == Booking.NO_SHOW:
            return Response(
                {"detail": "No-show bookings cannot be rescheduled."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = BookingRescheduleSerializer(
            booking,
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        booking = serializer.save()

        try:
            ticket = booking.queueticket
        except QueueTicket.DoesNotExist:
            ticket = None

        if ticket:
            ticket.queue_type = determine_queue_type(booking)
            ticket.queue_number = generate_queue_number(booking, ticket.queue_type)
            ticket.status = QueueTicket.SCHEDULED
            ticket.assigned_counter = None
            ticket.save(
                update_fields=[
                    "queue_type",
                    "queue_number",
                    "status",
                    "assigned_counter",
                ]
            )
        else:
            create_queue_ticket_for_booking(booking)

        # A rescheduled appointment must be activated into the live queue again
        # after its new six-hour check-in window opens.
        booking.checked_in_at = None
        booking.status = Booking.PENDING
        booking.save(update_fields=["checked_in_at", "status"])

        return Response(
            BookingListSerializer(booking).data,
            status=status.HTTP_200_OK,
        )
