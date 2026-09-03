from django.contrib.auth import (
    authenticate,
    login as auth_login,
    logout as auth_logout,
    update_session_auth_hash,
)
from django.contrib.auth.models import User
from django.middleware.csrf import get_token
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from rest_framework import status
from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from .models import Profile
from .permissions import IsSystemAdmin
from .serializers import (
    AccountSerializer,
    ChangePasswordSerializer,
    CustomerRegistrationSerializer,
    StaffAccountCreateSerializer,
    StaffAccountSerializer,
    StaffAccountUpdateSerializer,
)


def is_last_active_system_admin(user):
    """Return True when removing this admin role/state would orphan the control plane."""

    if user.profile.role != Profile.SYSTEM_ADMIN or not user.is_active:
        return False
    return (
        User.objects.filter(
            profile__role=Profile.SYSTEM_ADMIN,
            is_active=True,
        ).count()
        <= 1
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


@method_decorator(ensure_csrf_cookie, name="dispatch")
class CSRFTokenAPIView(APIView):
    """Issue the CSRF cookie/token required before a browser session login."""

    permission_classes = [AllowAny]

    def get(self, request):
        return Response({"csrfToken": get_token(request)})


@method_decorator(csrf_protect, name="dispatch")
class LoginAPIView(APIView):
    """Authenticate username/password and start a CSRF-protected Django session."""

    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

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


class ChangePasswordAPIView(APIView):
    """Allow an authenticated user to rotate their own password safely."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "account_security"

    def post(self, request):
        serializer = ChangePasswordSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        # Changing a Django password changes the session auth hash. Preserve the
        # current trusted session instead of unexpectedly logging the user out.
        update_session_auth_hash(request, user)

        return Response(
            {"detail": "Password changed successfully."},
            status=status.HTTP_200_OK,
        )


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

        requested_role = serializer.validated_data.get("role", user.profile.role)
        if (
            requested_role != Profile.SYSTEM_ADMIN
            and is_last_active_system_admin(user)
        ):
            return Response(
                {"detail": "Smart Q must retain at least one active System Admin."},
                status=status.HTTP_409_CONFLICT,
            )

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

        if requested_state is False and is_last_active_system_admin(user):
            return Response(
                {"detail": "Smart Q must retain at least one active System Admin."},
                status=status.HTTP_409_CONFLICT,
            )

        user.is_active = requested_state
        user.save(update_fields=["is_active"])
        return Response(StaffAccountSerializer(user).data)
