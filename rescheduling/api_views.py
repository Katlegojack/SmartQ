from datetime import date

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsBranchManager
from branches.models import Branch
from notifications.services import create_notification_for_unnotified_impacts
from queues.disruptions import (
    create_disruption_impact_records,
    get_disruption_report,
    pause_queue,
    resume_queue,
)
from queues.models import QueuePause
from services.availability import get_branch_service
from services.models import Service

from .services import create_reschedule_recommendations_for_risk_impacts


def parse_iso_date(raw_value):
    """Parse YYYY-MM-DD input without leaking Python parsing exceptions."""
    if not raw_value:
        return None, "booking_date is required and must use YYYY-MM-DD format."
    try:
        return date.fromisoformat(raw_value), None
    except (TypeError, ValueError):
        return None, "booking_date is required and must use YYYY-MM-DD format."


def queue_pause_response(queue_pause):
    """Return the live disruption report plus stable pause identity."""
    return get_disruption_report(queue_pause)


class BranchQueuePauseCreateAPIView(APIView):
    """Allow a Branch Manager/Admin to pause one offered service in a branch."""

    permission_classes = [IsBranchManager]

    def post(self, request, branch_id):
        branch = get_object_or_404(Branch, pk=branch_id, is_active=True)
        self.check_object_permissions(request, branch)

        service_id = request.data.get("service_id")
        service = get_object_or_404(Service, pk=service_id, is_active=True)
        if get_branch_service(branch, service) is None:
            return Response(
                {"detail": "This service is not currently offered by the branch."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        booking_date, error = parse_iso_date(request.data.get("booking_date"))
        if error:
            return Response({"detail": error}, status=status.HTTP_400_BAD_REQUEST)

        queue_pause = pause_queue(
            branch,
            service,
            booking_date,
            reason=request.data.get("reason", "").strip(),
        )
        return Response(
            queue_pause_response(queue_pause),
            status=status.HTTP_201_CREATED,
        )


class QueuePauseDetailAPIView(APIView):
    """Return a live impact preview for one authorised queue pause."""

    permission_classes = [IsBranchManager]

    def get(self, request, pause_id):
        queue_pause = get_object_or_404(
            QueuePause.objects.select_related("branch", "service"),
            pk=pause_id,
        )
        self.check_object_permissions(request, queue_pause)
        return Response(queue_pause_response(queue_pause), status=status.HTTP_200_OK)


class QueuePauseResumeAPIView(APIView):
    """
    End a disruption and finalize its impact/recommendation snapshot.

    Risk is persisted only after resume so lost service capacity is based on the
    finished pause duration rather than a moving active-pause estimate.
    """

    permission_classes = [IsBranchManager]

    def post(self, request, pause_id):
        queue_pause = get_object_or_404(
            QueuePause.objects.select_related("branch", "service"),
            pk=pause_id,
        )
        self.check_object_permissions(request, queue_pause)

        resume_queue(queue_pause)
        impact_result = create_disruption_impact_records(queue_pause)
        notification_result = create_notification_for_unnotified_impacts(queue_pause)
        recommendation_result = create_reschedule_recommendations_for_risk_impacts(
            queue_pause
        )

        queue_pause.refresh_from_db()
        return Response(
            {
                "disruption": queue_pause_response(queue_pause),
                "impact_processing": impact_result,
                "notification_processing": notification_result,
                "rescheduling": recommendation_result,
            },
            status=status.HTTP_200_OK,
        )
