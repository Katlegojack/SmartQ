from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import AccountSerializer, CustomerRegistrationSerializer


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

        # Smart Q APIs depend on Profile for role/priority information. Refuse a
        # partially-created account rather than allowing ambiguous authorization.
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
