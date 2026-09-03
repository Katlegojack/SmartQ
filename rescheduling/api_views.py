from datetime import date

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
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

from .models import RescheduleOption, RescheduleRecommendation
from .services import (
    RescheduleWorkflowError,
    create_reschedule_recommendations_for_risk_impacts,
    select_and_apply_reschedule_option,
)


def parse_iso_date(raw_value):
    if not raw_value:
        return None, "booking_date is required and must use YYYY-MM-DD format."
    try:
        return date.fromisoformat(raw_value), None
    except (TypeError, ValueError):
        return None, "booking_date is required and must use YYYY-MM-DD format."


def queue_pause_response(queue_pause):
    return get_disruption_report(queue_pause)


def recommendation_response(recommendation):
    options = recommendation.option.order_by("option_date", "option_time", "id")
    return {
        "id": recommendation.id,
        "booking_id": recommendation.booking_id,
        "old_booking_date": recommendation.old_booking_date,
        "old_booking_time": recommendation.old_booking_time,
        "suggested_booking_date": recommendation.suggested_booking_date,
        "suggested_booking_time": recommendation.suggested_booking_time,
        "priority_on_reschedule": recommendation.priority_on_reschedule,
        "reason": recommendation.reason,
        "status": recommendation.status,
        "applied_at": recommendation.applied_at,
        "options": [
            {
                "id": option.id,
                "option_date": option.option_date,
                "option_time": option.option_time,
                "capacity": option.capacity,
                "booked_count": option.booked_count,
                "available_count": option.available_count,
                "is_recommended": option.is_recommended,
                "is_selected": option.is_selected,
            }
            for option in options
        ],
    }


def reschedule_error_response(error_code):
    if error_code in {"slot_full", "past_slot", "past_date", "invalid_slot"}:
        messages = {
            "slot_full": "That replacement slot is no longer available. Choose another option.",
            "past_slot": "That replacement slot has already passed.",
            "past_date": "That replacement date has already passed.",
            "invalid_slot": "That replacement time is no longer a valid branch slot.",
        }
        return Response(
            {"detail": messages[error_code], "code": error_code},
            status=status.HTTP_409_CONFLICT,
        )
    if error_code == "service_not_offered":
        return Response(
            {"detail": "The service is no longer offered at this branch.", "code": error_code},
            status=status.HTTP_409_CONFLICT,
        )
    return Response(
        {"detail": "This reschedule option can no longer be applied.", "code": error_code},
        status=status.HTTP_409_CONFLICT,
    )


class BranchQueuePauseCreateAPIView(APIView):
    permission_classes = [IsBranchManager]

    def get(self, request, branch_id):
        """Restore branch disruption history/state for authorised managers/admins."""
        branch = get_object_or_404(Branch, pk=branch_id, is_active=True)
        self.check_object_permissions(request, branch)
        pauses = QueuePause.objects.filter(branch=branch).select_related(
            "branch",
            "service",
        ).order_by("-is_active", "-started_at", "-id")
        return Response(
            {
                "branch_id": branch.id,
                "pauses": [queue_pause_response(item) for item in pauses],
            },
            status=status.HTTP_200_OK,
        )

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
        return Response(queue_pause_response(queue_pause), status=status.HTTP_201_CREATED)


class QueuePauseDetailAPIView(APIView):
    permission_classes = [IsBranchManager]

    def get(self, request, pause_id):
        queue_pause = get_object_or_404(
            QueuePause.objects.select_related("branch", "service"),
            pk=pause_id,
        )
        self.check_object_permissions(request, queue_pause)
        return Response(queue_pause_response(queue_pause), status=status.HTTP_200_OK)


class QueuePauseResumeAPIView(APIView):
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
        recommendation_result = create_reschedule_recommendations_for_risk_impacts(queue_pause)
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


class MyRescheduleRecommendationListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        recommendations = (
            RescheduleRecommendation.objects.filter(booking__user=request.user)
            .select_related("booking", "ticket", "disruption_impact")
            .prefetch_related("option")
            .order_by("-created_at", "-id")
        )
        return Response(
            [recommendation_response(item) for item in recommendations],
            status=status.HTTP_200_OK,
        )


class CustomerRescheduleOptionSelectAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, option_id):
        option = get_object_or_404(
            RescheduleOption.objects.select_related(
                "recommendation",
                "recommendation__booking",
            ),
            pk=option_id,
            recommendation__booking__user=request.user,
        )
        try:
            recommendation = select_and_apply_reschedule_option(
                option,
                actor=request.user,
            )
        except RescheduleWorkflowError as exc:
            return reschedule_error_response(exc.code)

        recommendation.refresh_from_db()
        return Response(
            recommendation_response(recommendation),
            status=status.HTTP_200_OK,
        )
