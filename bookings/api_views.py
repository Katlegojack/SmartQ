from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.generics import CreateAPIView, ListAPIView, RetrieveAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import Profile
from accounts.permissions import IsQueueViewer, get_user_profile
from branches.models import Branch
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
    GuestWalkInSerializer,
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
    if error_code == "expired_cancelled":
        return Response(
            {
                "detail": (
                    "The appointment time passed before check-in. "
                    "The booking has been cancelled and was never added to the live queue."
                )
            },
            status=status.HTTP_409_CONFLICT,
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


def get_staff_branch(request):
    """
    Resolve the branch for a reception workflow.

    Branch-scoped staff always use their assigned branch. SYSTEM_ADMIN is global
    and must explicitly provide branch_id so a global account never searches or
    creates walk-ins in an unintended branch.
    """
    profile = get_user_profile(request.user)
    if profile is None:
        return None, Response(
            {"detail": "A Smart Q staff profile is required."},
            status=status.HTTP_403_FORBIDDEN,
        )

    if profile.role != Profile.SYSTEM_ADMIN:
        return profile.branch, None

    branch_id = request.query_params.get("branch_id") or request.data.get("branch_id")
    if not branch_id:
        return None, Response(
            {"detail": "System administrators must provide branch_id."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    branch = get_object_or_404(Branch, pk=branch_id, is_active=True)
    return branch, None


class BookingCreateAPIView(CreateAPIView):
    """Create a scheduled online booking and its non-live queue ticket."""

    serializer_class = BookingCreateSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        with transaction.atomic():
            booking = serializer.save(user=self.request.user, source=Booking.ONLINE)
            if not QueueTicket.objects.filter(booking=booking).exists():
                create_queue_ticket_for_booking(booking)


class MyBookingListAPIView(ListAPIView):
    serializer_class = BookingListSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Booking.objects.filter(user=self.request.user).select_related(
            "branch", "service", "user", "guest_customer"
        ).order_by("-created_at")


class BookingDetailAPIView(RetrieveAPIView):
    serializer_class = BookingListSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Booking.objects.filter(user=self.request.user).select_related(
            "branch", "service", "user", "guest_customer"
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
            Booking.objects.select_related(
                "branch", "service", "user", "guest_customer"
            ),
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


class ReceptionBookingSearchAPIView(APIView):
    """Search customers/bookings only inside the authorised reception branch."""

    permission_classes = [IsQueueViewer]

    def get(self, request):
        branch, error_response = get_staff_branch(request)
        if error_response:
            return error_response

        query = request.query_params.get("q", "").strip()
        if len(query) < 2:
            return Response(
                {"detail": "Provide at least 2 characters in q."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        filters = (
            Q(user__username__icontains=query)
            | Q(user__first_name__icontains=query)
            | Q(user__last_name__icontains=query)
            | Q(user__email__icontains=query)
            | Q(guest_customer__full_name__icontains=query)
            | Q(guest_customer__phone_number__icontains=query)
        )

        if query.isdigit():
            filters |= Q(pk=int(query))

        bookings = (
            Booking.objects.filter(branch=branch)
            .filter(filters)
            .select_related("branch", "service", "user", "guest_customer")
            .order_by("-booking_date", "-booking_time")[:50]
        )

        return Response(
            BookingListSerializer(bookings, many=True).data,
            status=status.HTTP_200_OK,
        )


class ReceptionGuestWalkInAPIView(APIView):
    """Create a no-account guest walk-in and immediately join the live queue."""

    permission_classes = [IsQueueViewer]

    def post(self, request):
        branch, error_response = get_staff_branch(request)
        if error_response:
            return error_response

        serializer = GuestWalkInSerializer(
            data=request.data,
            context={"branch": branch},
        )
        serializer.is_valid(raise_exception=True)
        booking = serializer.save()

        return Response(
            BookingListSerializer(booking).data,
            status=status.HTTP_201_CREATED,
        )


class BookingCancelAPIView(APIView):
    """Cancel an eligible registered-customer booking and connected ticket."""

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
    """Move a registered booking and require fresh check-in for the new slot."""

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

        booking.checked_in_at = None
        booking.status = Booking.PENDING
        booking.save(update_fields=["checked_in_at", "status"])

        return Response(
            BookingListSerializer(booking).data,
            status=status.HTTP_200_OK,
        )
