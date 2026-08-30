from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.generics import CreateAPIView, ListAPIView, RetrieveAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from queues.models import QueueTicket
from queues.services import (
    create_queue_ticket_for_booking,
    determine_queue_type,
    generate_queue_number,
)
from .models import Booking
from .serializers import (
    BookingCreateSerializer,
    BookingListSerializer,
    BookingRescheduleSerializer,
)


class BookingCreateAPIView(CreateAPIView):
    """Create a booking for the logged-in customer and generate its queue ticket."""

    serializer_class = BookingCreateSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        # Booking + ticket creation must either both succeed or both roll back.
        with transaction.atomic():
            booking = serializer.save(user=self.request.user)
            if not QueueTicket.objects.filter(booking=booking).exists():
                create_queue_ticket_for_booking(booking)


class MyBookingListAPIView(ListAPIView):
    """Return only bookings owned by the logged-in customer."""

    serializer_class = BookingListSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Booking.objects.filter(user=self.request.user).select_related(
            "branch", "service"
        ).order_by("-created_at")


class BookingDetailAPIView(RetrieveAPIView):
    """Return one booking only when it belongs to the logged-in customer."""

    serializer_class = BookingListSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Restricting the queryset prevents one customer from reading another
        # customer's booking simply by guessing its database ID.
        return Booking.objects.filter(user=self.request.user).select_related(
            "branch", "service"
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

        # Cancellation is idempotent: repeating the request is safe.
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
    """Move an eligible booking to a new date/time and reset its queue ticket."""

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
            # A new date changes the customer's place in that day's queue, so
            # queue type/number are recalculated and the ticket returns to WAITING.
            ticket.queue_type = determine_queue_type(booking)
            ticket.queue_number = generate_queue_number(booking, ticket.queue_type)
            ticket.status = QueueTicket.WAITING
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

        # A rescheduled booking is active again but has not yet been served.
        if booking.status != Booking.PENDING:
            booking.status = Booking.PENDING
            booking.save(update_fields=["status"])

        return Response(
            BookingListSerializer(booking).data,
            status=status.HTTP_200_OK,
        )
