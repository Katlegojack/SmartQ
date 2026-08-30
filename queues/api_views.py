from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from branches.models import Branch
from counters.models import Counter
from .models import QueueTicket
from .permissions import IsQueueStaff
from .serializers import QueueTicketSerializer
from .services import (
    call_next_ticket,
    complete_current_ticket,
    get_current_ticket,
    get_waiting_tickets,
    mark_current_ticket_no_show,
)
from .waiting_time import get_ticket_prediction


class CallNextTicketAPIView(APIView):
    """Call the next waiting customer for a specific counter."""

    # Counter operation is a staff action, not a normal customer action.
    permission_classes = [IsQueueStaff]

    def post(self, request, counter_id):
        counter = get_object_or_404(Counter, pk=counter_id)

        if counter.status != Counter.OPEN:
            return Response(
                {"detail": "This counter must be open before calling customers."},
                status=status.HTTP_409_CONFLICT,
            )

        ticket = call_next_ticket(counter)

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

        return Response(
            QueueTicketSerializer(ticket).data,
            status=status.HTTP_200_OK,
        )


class CompleteCurrentTicketAPIView(APIView):
    """Complete the customer currently being served at a counter."""

    permission_classes = [IsQueueStaff]

    def post(self, request, counter_id):
        counter = get_object_or_404(Counter, pk=counter_id)
        ticket = complete_current_ticket(counter)

        if ticket is None:
            return Response(
                {"detail": "This counter is not serving any customer."},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(
            QueueTicketSerializer(ticket).data,
            status=status.HTTP_200_OK,
        )


class NoShowCurrentTicketAPIView(APIView):
    """Mark the customer currently being served as a no-show."""

    permission_classes = [IsQueueStaff]

    def post(self, request, counter_id):
        counter = get_object_or_404(Counter, pk=counter_id)
        ticket = mark_current_ticket_no_show(counter)

        if ticket is None:
            return Response(
                {"detail": "This counter is not serving any customer."},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(
            QueueTicketSerializer(ticket).data,
            status=status.HTTP_200_OK,
        )


class CurrentCounterTicketAPIView(APIView):
    """Return the customer currently being served at a counter."""

    permission_classes = [IsQueueStaff]

    def get(self, request, counter_id):
        counter = get_object_or_404(Counter, pk=counter_id)
        ticket = get_current_ticket(counter)

        if ticket is None:
            return Response(
                {"detail": "This counter is currently free."},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(QueueTicketSerializer(ticket).data)


class BranchWaitingQueueAPIView(APIView):
    """Return today's waiting queue for a branch for staff dashboards."""

    permission_classes = [IsQueueStaff]

    def get(self, request, branch_id):
        branch = get_object_or_404(Branch, pk=branch_id, is_active=True)
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
    """
    Return the logged-in customer's active ticket and current queue prediction.

    This is the API the customer queue-tracker screen can poll while waiting.
    """

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

        # Once the customer is already being served, there is no remaining wait.
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
