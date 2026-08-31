from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import Profile
from accounts.permissions import (
    IsBranchManager,
    IsQueueOperator,
    IsQueueViewer,
    get_user_profile,
)
from branches.models import Branch
from .models import Counter
from .serializers import CounterSerializer
from .services import (
    assign_counter_staff,
    close_counter,
    open_counter,
    pause_counter,
    resume_counter,
    unassign_counter_staff,
)


def counter_error_response(error_code):
    """Translate counter-domain outcomes into stable HTTP responses."""
    responses = {
        "invalid_staff_role": (
            "Only a user with the Counter Staff role can be assigned to a counter.",
            status.HTTP_400_BAD_REQUEST,
        ),
        "wrong_branch": (
            "Counter Staff must belong to the same branch as the counter.",
            status.HTTP_400_BAD_REQUEST,
        ),
        "counter_not_closed": (
            "Staff assignment can change only while the counter is closed.",
            status.HTTP_409_CONFLICT,
        ),
        "counter_busy": (
            "Resolve the customer currently being served before closing or changing staff.",
            status.HTTP_409_CONFLICT,
        ),
        "staff_already_assigned": (
            "This staff member is already assigned to another counter.",
            status.HTTP_409_CONFLICT,
        ),
        "unassigned": (
            "Assign Counter Staff before opening this counter.",
            status.HTTP_409_CONFLICT,
        ),
        "already_open": ("This counter is already open.", status.HTTP_409_CONFLICT),
        "use_resume": (
            "This counter is paused. Resume it instead of opening it again.",
            status.HTTP_409_CONFLICT,
        ),
        "not_open": ("Only an open counter can be paused.", status.HTTP_409_CONFLICT),
        "not_paused": ("Only a paused counter can be resumed.", status.HTTP_409_CONFLICT),
        "already_closed": ("This counter is already closed.", status.HTTP_409_CONFLICT),
    }
    detail, response_status = responses.get(
        error_code,
        ("The counter operation could not be completed.", status.HTTP_400_BAD_REQUEST),
    )
    return Response({"detail": detail}, status=response_status)


def counter_operator_denied(request, counter):
    """
    Return True when Counter Staff tries to operate a counter not assigned to them.

    Branch Managers and System Admins retain operational override inside their
    existing branch/global permission scope.
    """
    profile = get_user_profile(request.user)
    return (
        profile is not None
        and profile.role == Profile.COUNTER_STAFF
        and counter.assigned_staff_id != request.user.id
    )


class BranchCounterListAPIView(APIView):
    """List counters visible to authorised staff for one branch."""

    permission_classes = [IsQueueViewer]

    def get(self, request, branch_id):
        branch = get_object_or_404(Branch, pk=branch_id, is_active=True)
        self.check_object_permissions(request, branch)

        counters = Counter.objects.filter(branch=branch).select_related(
            "branch", "assigned_staff"
        ).order_by("counter_number")
        return Response(CounterSerializer(counters, many=True).data)


class MyAssignedCounterAPIView(APIView):
    """Return the counter assigned to the logged-in Counter Staff user."""

    permission_classes = [IsQueueOperator]

    def get(self, request):
        profile = get_user_profile(request.user)
        if profile is None or profile.role != Profile.COUNTER_STAFF:
            return Response(
                {"detail": "This endpoint is for Counter Staff assignments."},
                status=status.HTTP_403_FORBIDDEN,
            )

        counter = Counter.objects.filter(assigned_staff=request.user).select_related(
            "branch", "assigned_staff"
        ).first()
        if counter is None:
            return Response(
                {"detail": "You are not currently assigned to a counter."},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(CounterSerializer(counter).data)


class CounterAssignStaffAPIView(APIView):
    """Allow Branch Manager/System Admin to assign one Counter Staff user."""

    permission_classes = [IsBranchManager]

    def post(self, request, counter_id):
        counter = get_object_or_404(Counter, pk=counter_id)
        self.check_object_permissions(request, counter)

        staff_user_id = request.data.get("staff_user_id")
        if not staff_user_id:
            return Response(
                {"detail": "staff_user_id is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        staff_user = get_object_or_404(User, pk=staff_user_id)
        counter, error_code = assign_counter_staff(counter, staff_user)
        if error_code:
            return counter_error_response(error_code)

        return Response(CounterSerializer(counter).data, status=status.HTTP_200_OK)


class CounterUnassignStaffAPIView(APIView):
    """Allow Branch Manager/System Admin to remove a counter assignment safely."""

    permission_classes = [IsBranchManager]

    def post(self, request, counter_id):
        counter = get_object_or_404(Counter, pk=counter_id)
        self.check_object_permissions(request, counter)

        counter, error_code = unassign_counter_staff(counter)
        if error_code:
            return counter_error_response(error_code)

        return Response(CounterSerializer(counter).data, status=status.HTTP_200_OK)


class CounterLifecycleAPIView(APIView):
    """Base class for OPEN/PAUSE/RESUME/CLOSE counter actions."""

    permission_classes = [IsQueueOperator]
    lifecycle_service = None

    def post(self, request, counter_id):
        counter = get_object_or_404(Counter, pk=counter_id)
        self.check_object_permissions(request, counter)

        if counter_operator_denied(request, counter):
            return Response(
                {"detail": "Counter Staff may operate only their assigned counter."},
                status=status.HTTP_403_FORBIDDEN,
            )

        counter, error_code = self.lifecycle_service(counter)
        if error_code:
            return counter_error_response(error_code)

        return Response(CounterSerializer(counter).data, status=status.HTTP_200_OK)


class CounterOpenAPIView(CounterLifecycleAPIView):
    lifecycle_service = staticmethod(open_counter)


class CounterPauseAPIView(CounterLifecycleAPIView):
    lifecycle_service = staticmethod(pause_counter)


class CounterResumeAPIView(CounterLifecycleAPIView):
    lifecycle_service = staticmethod(resume_counter)


class CounterCloseAPIView(CounterLifecycleAPIView):
    lifecycle_service = staticmethod(close_counter)
