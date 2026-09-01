from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Profile
from .permissions import IsSystemAdmin
from .serializers import (
    AccountSerializer,
    CustomerRegistrationSerializer,
    StaffAccountCreateSerializer,
    StaffAccountSerializer,
    StaffAccountUpdateSerializer,
)


class CustomerRegistrationAPIView(APIView):
    """Create a new Smart Q customer account and profile."""

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = CustomerRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        return Response(
            AccountSerializer(user).data,
            status=status.HTTP_201_CREATED,
        )


class LoginAPIView(APIView):
    """
    Authenticate username/password and start a Django session.

    Day 29 intentionally uses Django's built-in session authentication instead
    of adding an unreviewed JWT dependency. This is a secure foundation for the
    current Django/DRF application. Cross-origin production frontend deployment
    will require an explicit CORS/CSRF/cookie strategy before launch.
    """

    permission_classes = [AllowAny]

    def post(self, request):
        username = request.data.get("username")
        password = request.data.get("password")

        if not username or not password:
            return Response(
                {"detail": "Username and password are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = authenticate(request, username=username, password=password)
        if user is None:
            return Response(
                {"detail": "Invalid username or password."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if not hasattr(user, "profile"):
            return Response(
                {"detail": "This account is missing its Smart Q profile."},
                status=status.HTTP_403_FORBIDDEN,
            )

        auth_login(request, user)

        return Response(
            {
                "detail": "Login successful.",
                "user": AccountSerializer(user).data,
            },
            status=status.HTTP_200_OK,
        )


class LogoutAPIView(APIView):
    """End the authenticated user's Django session."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        auth_logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class CurrentAccountAPIView(APIView):
    """Return the logged-in user's identity, Smart Q role, and branch scope."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not hasattr(request.user, "profile"):
            return Response(
                {"detail": "This account is missing its Smart Q profile."},
                status=status.HTTP_409_CONFLICT,
            )

        return Response(AccountSerializer(request.user).data)


class StaffAccountListCreateAPIView(ListAPIView):
    """Allow only a Smart Q System Admin to list or create operational staff."""

    permission_classes = [IsAuthenticated, IsSystemAdmin]
    serializer_class = StaffAccountSerializer

    def get_queryset(self):
        return (
            User.objects.filter(profile__role__in=Profile.STAFF_ROLES)
            .select_related("profile", "profile__branch")
            .order_by("username")
        )

    def post(self, request):
        serializer = StaffAccountCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(
            StaffAccountSerializer(user).data,
            status=status.HTTP_201_CREATED,
        )


class StaffAccountDetailAPIView(APIView):
    """Read or safely update one operational Smart Q staff account."""

    permission_classes = [IsAuthenticated, IsSystemAdmin]

    def get_object(self, pk):
        return get_object_or_404(
            User.objects.select_related("profile", "profile__branch"),
            pk=pk,
            profile__role__in=Profile.STAFF_ROLES,
        )

    def get(self, request, pk):
        user = self.get_object(pk)
        return Response(StaffAccountSerializer(user).data)

    def patch(self, request, pk):
        user = self.get_object(pk)
        serializer = StaffAccountUpdateSerializer(
            user,
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        user.refresh_from_db()
        return Response(StaffAccountSerializer(user).data)


class StaffAccountActivationAPIView(APIView):
    """Activate or deactivate an operational staff account without deleting history."""

    permission_classes = [IsAuthenticated, IsSystemAdmin]

    def patch(self, request, pk):
        user = get_object_or_404(
            User.objects.select_related("profile"),
            pk=pk,
            profile__role__in=Profile.STAFF_ROLES,
        )

        requested_state = request.data.get("is_active")
        if not isinstance(requested_state, bool):
            return Response(
                {"detail": "is_active must be true or false."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if user.pk == request.user.pk and requested_state is False:
            return Response(
                {"detail": "A System Admin cannot deactivate their own active session account."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if (
            user.profile.role == Profile.SYSTEM_ADMIN
            and user.is_active
            and requested_state is False
        ):
            active_admin_count = User.objects.filter(
                profile__role=Profile.SYSTEM_ADMIN,
                is_active=True,
            ).count()
            if active_admin_count <= 1:
                return Response(
                    {"detail": "Smart Q must retain at least one active System Admin."},
                    status=status.HTTP_409_CONFLICT,
                )

        user.is_active = requested_state
        user.save(update_fields=["is_active"])
        return Response(StaffAccountSerializer(user).data)
