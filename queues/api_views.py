from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import Profile
from accounts.permissions import (
    IsBranchManager,
    IsQueueOperator,
    IsQueueViewer,
    get_user_profile,
)
from bookings.models import Booking
from branches.models import Branch
from counters.models import Counter
from .events import get_booking_event_timeline
from .models import QueueEvent, QueueTicket
from .serializers import QueueTicketSerializer
from .services import (
    call_next_ticket,
    complete_current_ticket,
    get_current_ticket,
    get_waiting_tickets,
    mark_current_ticket_no_show,
)
from .waiting_time import get_ticket_prediction


def counter_staff_assignment_error(request, counter):
    """Protect counter mutations from same-branch but unassigned Counter Staff."""
    profile = get_user_profile(request.user)
    if (
        profile is not None
        and profile.role == Profile.COUNTER_STAFF
        and counter.assigned_staff_id != request.user.id
    ):
        return Response(
            {"detail": "Counter Staff may operate only their assigned counter."},
            status=status.HTTP_403_FORBIDDEN,
        )
    return None


def customer_event_response(event):
    """Return only customer-relevant lifecycle facts for one owned booking."""
    return {
        "id": event.id,
        "event_type": event.event_type,
        "queue_number": event.queue_number,
        "queue_type": event.queue_type,
        "from_ticket_status": event.from_ticket_status,
        "to_ticket_status": event.to_ticket_status,
        "from_booking_status": event.from_booking_status,
        "to_booking_status": event.to_booking_status,
        "counter_id": event.counter_id,
        "occurred_at": event.occurred_at,
    }


def manager_event_response(event):
    """Return an operational audit representation for authorised management."""
    return {
        "id": event.id,
        "event_type": event.event_type,
        "source": event.source,
        "actor_user_id": event.actor_id,
        "actor_username": event.actor_username,
        "actor_role": event.actor_role,
        "booking_id": event.booking_id,
        "ticket_id": event.ticket_id,
        "counter_id": event.counter_id,
        "branch_id": event.branch_id,
        "service_id": event.service_id,
        "queue_number": event.queue_number,
        "queue_type": event.queue_type,
        "from_ticket_status": event.from_ticket_status,
        "to_ticket_status": event.to_ticket_status,
        "from_booking_status": event.from_booking_status,
        "to_booking_status": event.to_booking_status,
        "metadata": event.metadata,
        "occurred_at": event.occurred_at,
    }


class CallNextTicketAPIView(APIView):
    """Call the next waiting customer for a staffed OPEN counter."""
    permission_classes = [IsQueueOperator]

    def post(self, request, counter_id):
        counter = get_object_or_404(Counter, pk=counter_id)
        self.check_object_permissions(request, counter)

        assignment_error = counter_staff_assignment_error(request, counter)
        if assignment_error:
            return assignment_error

        if counter.status != Counter.OPEN:
            return Response(
                {"detail": "This counter must be open before calling customers."},
                status=status.HTTP_409_CONFLICT,
            )
        if counter.assigned_staff_id is None:
            return Response(
                {"detail": "Assign Counter Staff before calling customers."},
                status=status.HTTP_409_CONFLICT,
            )

        ticket = call_next_ticket(counter, actor=request.user)
        if ticket is None:
            return Response(
                {
                    "detail": (
                        "No customer can be called. The counter may already be serving "
                        "someone or no matching customers are waiting today."
                    )
                },
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(QueueTicketSerializer(ticket).data, status=status.HTTP_200_OK)


class CompleteCurrentTicketAPIView(APIView):
    """Complete the customer currently being served at an authorised counter."""
    permission_classes = [IsQueueOperator]

    def post(self, request, counter_id):
        counter = get_object_or_404(Counter, pk=counter_id)
        self.check_object_permissions(request, counter)

        assignment_error = counter_staff_assignment_error(request, counter)
        if assignment_error:
            return assignment_error

        ticket = complete_current_ticket(counter, actor=request.user)
        if ticket is None:
            return Response(
                {"detail": "This counter is not serving any customer."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(QueueTicketSerializer(ticket).data, status=status.HTTP_200_OK)


class NoShowCurrentTicketAPIView(APIView):
    """Mark the current customer as a no-show at an authorised counter."""
    permission_classes = [IsQueueOperator]

    def post(self, request, counter_id):
        counter = get_object_or_404(Counter, pk=counter_id)
        self.check_object_permissions(request, counter)

        assignment_error = counter_staff_assignment_error(request, counter)
        if assignment_error:
            return assignment_error

        ticket = mark_current_ticket_no_show(counter, actor=request.user)
        if ticket is None:
            return Response(
                {"detail": "This counter is not serving any customer."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(QueueTicketSerializer(ticket).data, status=status.HTTP_200_OK)


class CurrentCounterTicketAPIView(APIView):
    """Return the ticket currently served at a counter visible to this staff user."""
    permission_classes = [IsQueueViewer]

    def get(self, request, counter_id):
        counter = get_object_or_404(Counter, pk=counter_id)
        self.check_object_permissions(request, counter)
        ticket = get_current_ticket(counter)
        if ticket is None:
            return Response(
                {"detail": "This counter is currently free."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(QueueTicketSerializer(ticket).data)


class BranchWaitingQueueAPIView(APIView):
    """Return today's waiting queue when the staff user may view this branch."""
    permission_classes = [IsQueueViewer]

    def get(self, request, branch_id):
        branch = get_object_or_404(Branch, pk=branch_id, is_active=True)
        self.check_object_permissions(request, branch)
        queue_type = request.query_params.get("queue_type")

        if queue_type and queue_type not in [QueueTicket.GENERAL, QueueTicket.PRIORITY]:
            return Response(
                {"detail": "queue_type must be either 'general' or 'priority'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        tickets = get_waiting_tickets(
            branch=branch,
            booking_date=timezone.localdate(),
            queue_type=queue_type,
        )
        return Response(QueueTicketSerializer(tickets, many=True).data)


class MyCurrentQueueTicketAPIView(APIView):
    """Return the logged-in customer's active ticket and current queue prediction."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        ticket = QueueTicket.objects.filter(
            booking__user=request.user,
            booking__booking_date=timezone.localdate(),
            status__in=[QueueTicket.WAITING, QueueTicket.SERVING],
        ).select_related(
            "booking",
            "booking__branch",
            "booking__service",
            "booking__user",
        ).order_by("-created_at").first()

        if ticket is None:
            return Response(
                {"detail": "You do not have an active queue ticket for today."},
                status=status.HTTP_404_NOT_FOUND,
            )

        prediction = get_ticket_prediction(ticket)
        if ticket.status == QueueTicket.SERVING:
            prediction["people_ahead"] = 0
            prediction["queue_position"] = 0
            prediction["estimated_wait_time"] = 0

        return Response(
            {
                "ticket": QueueTicketSerializer(ticket).data,
                "prediction": prediction,
            }
        )


class CustomerBookingTimelineAPIView(APIView):
    """Return lifecycle history only for a booking owned by the logged-in customer."""
    permission_classes = [IsAuthenticated]

    def get(self, request, booking_id):
        booking = get_object_or_404(
            Booking.objects.select_related("branch", "service"),
            pk=booking_id,
            user=request.user,
        )
        events = get_booking_event_timeline(booking)
        return Response(
            {
                "booking_id": booking.id,
                "events": [customer_event_response(event) for event in events],
            },
            status=status.HTTP_200_OK,
        )


class BranchQueueEventAuditAPIView(APIView):
    """Return branch audit history to own-branch Managers and global System Admins."""
    permission_classes = [IsBranchManager]

    def get(self, request, branch_id):
        branch = get_object_or_404(Branch, pk=branch_id, is_active=True)
        self.check_object_permissions(request, branch)

        events = QueueEvent.objects.filter(branch=branch).select_related(
            "booking",
            "ticket",
            "counter",
            "service",
            "actor",
        ).order_by("-occurred_at", "-id")

        return Response(
            {
                "branch_id": branch.id,
                "events": [manager_event_response(event) for event in events],
            },
            status=status.HTTP_200_OK,
        )
