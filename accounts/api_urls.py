from django.urls import path

from .api_views import (
    CSRFTokenAPIView,
    ChangePasswordAPIView,
    CurrentAccountAPIView,
    CustomerRegistrationAPIView,
    LoginAPIView,
    LogoutAPIView,
    StaffAccountActivationAPIView,
    StaffAccountDetailAPIView,
    StaffAccountListCreateAPIView,
)


urlpatterns = [
    path("register/", CustomerRegistrationAPIView.as_view(), name="api_register"),
    path("csrf/", CSRFTokenAPIView.as_view(), name="api_csrf_token"),
    path("login/", LoginAPIView.as_view(), name="api_login"),
    path("logout/", LogoutAPIView.as_view(), name="api_logout"),
    path("me/", CurrentAccountAPIView.as_view(), name="api_current_account"),
    path(
        "change-password/",
        ChangePasswordAPIView.as_view(),
        name="api_change_password",
    ),
    path(
        "admin/staff/",
        StaffAccountListCreateAPIView.as_view(),
        name="api_admin_staff_list_create",
    ),
    path(
        "admin/staff/<int:pk>/",
        StaffAccountDetailAPIView.as_view(),
        name="api_admin_staff_detail",
    ),
    path(
        "admin/staff/<int:pk>/activation/",
        StaffAccountActivationAPIView.as_view(),
        name="api_admin_staff_activation",
    ),
]
