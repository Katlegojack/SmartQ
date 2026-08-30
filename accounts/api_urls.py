from django.urls import path

from .api_views import (
    CurrentAccountAPIView,
    CustomerRegistrationAPIView,
    LoginAPIView,
    LogoutAPIView,
)


urlpatterns = [
    path("register/", CustomerRegistrationAPIView.as_view(), name="api_register"),
    path("login/", LoginAPIView.as_view(), name="api_login"),
    path("logout/", LogoutAPIView.as_view(), name="api_logout"),
    path("me/", CurrentAccountAPIView.as_view(), name="api_current_account"),
]
