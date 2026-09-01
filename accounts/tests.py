from datetime import date, time

from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from branches.models import Branch

from .models import Profile


class AccountAuthenticationAPITests(APITestCase):
    """Regression tests for Day 29 customer registration and session authentication."""

    def setUp(self):
        self.client = APIClient()
        self.registration_payload = {
            "username": "newcustomer",
            "password": "Strong-Test-Pass-482!",
            "first_name": "New",
            "last_name": "Customer",
            "email": "customer@example.com",
            "date_of_birth": "1998-05-20",
            "gender": Profile.OTHER,
            "disability_status": False,
        }

    def test_public_registration_creates_customer_profile(self):
        response = self.client.post(
            reverse("api_register"),
            self.registration_payload,
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        user = User.objects.get(username="newcustomer")
        self.assertTrue(user.check_password(self.registration_payload["password"]))
        self.assertEqual(user.profile.role, Profile.CUSTOMER)
        self.assertIsNone(user.profile.branch)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_registration_cannot_self_assign_system_admin_role(self):
        """Caller-supplied privilege fields must never create a staff account."""
        payload = {
            **self.registration_payload,
            "role": Profile.SYSTEM_ADMIN,
            "is_staff": True,
            "is_superuser": True,
            "branch": 999,
        }

        response = self.client.post(reverse("api_register"), payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(username="newcustomer")
        self.assertEqual(user.profile.role, Profile.CUSTOMER)
        self.assertIsNone(user.profile.branch)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_duplicate_username_is_rejected(self):
        User.objects.create_user(username="newcustomer", password="Existing-Pass-44!")

        response = self.client.post(
            reverse("api_register"),
            self.registration_payload,
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("username", response.data)

    def test_login_starts_session_and_me_returns_role(self):
        user = User.objects.create_user(
            username="customer",
            password="Strong-Test-Pass-482!",
            first_name="Test",
            last_name="Customer",
        )
        Profile.objects.create(
            user=user,
            date_of_birth=date(1995, 1, 1),
            gender=Profile.OTHER,
            role=Profile.CUSTOMER,
        )

        login_response = self.client.post(
            reverse("api_login"),
            {
                "username": "customer",
                "password": "Strong-Test-Pass-482!",
            },
            format="json",
        )
        me_response = self.client.get(reverse("api_current_account"))

        self.assertEqual(login_response.status_code, status.HTTP_200_OK)
        self.assertEqual(me_response.status_code, status.HTTP_200_OK)
        self.assertEqual(me_response.data["username"], "customer")
        self.assertEqual(me_response.data["role"], Profile.CUSTOMER)

    def test_invalid_login_is_rejected(self):
        user = User.objects.create_user(
            username="customer",
            password="Strong-Test-Pass-482!",
        )
        Profile.objects.create(
            user=user,
            date_of_birth=date(1995, 1, 1),
            gender=Profile.OTHER,
            role=Profile.CUSTOMER,
        )

        response = self.client.post(
            reverse("api_login"),
            {"username": "customer", "password": "wrong-password"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logout_ends_session(self):
        user = User.objects.create_user(
            username="customer",
            password="Strong-Test-Pass-482!",
        )
        Profile.objects.create(
            user=user,
            date_of_birth=date(1995, 1, 1),
            gender=Profile.OTHER,
            role=Profile.CUSTOMER,
        )
        self.client.login(username="customer", password="Strong-Test-Pass-482!")

        logout_response = self.client.post(reverse("api_logout"))
        me_response = self.client.get(reverse("api_current_account"))

        self.assertEqual(logout_response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertIn(
            me_response.status_code,
            [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN],
        )


class SystemAdminStaffManagementAPITests(APITestCase):
    """Day 37 tests for staff provisioning, scoping and safe deactivation."""

    def setUp(self):
        self.client = APIClient()
        self.branch = Branch.objects.create(
            branch_code="KIM001",
            name="Kimberley Branch",
            address="Civic Centre",
            city="Kimberley",
            opening_time=time(8, 0),
            closing_time=time(16, 30),
        )
        self.admin = self.create_account(
            username="sysadmin",
            role=Profile.SYSTEM_ADMIN,
            branch=None,
        )
        self.customer = self.create_account(
            username="customer",
            role=Profile.CUSTOMER,
            branch=None,
        )

    def create_account(self, username, role, branch):
        user = User.objects.create_user(
            username=username,
            password="Strong-Test-Pass-482!",
        )
        Profile.objects.create(
            user=user,
            date_of_birth=date(1990, 1, 1),
            gender=Profile.OTHER,
            role=role,
            branch=branch,
        )
        return user

    def staff_payload(self, **overrides):
        payload = {
            "username": "reception.one",
            "password": "Strong-Staff-Pass-482!",
            "first_name": "Reception",
            "last_name": "One",
            "email": "reception@example.com",
            "date_of_birth": "1992-04-05",
            "gender": Profile.OTHER,
            "disability_status": False,
            "role": Profile.RECEPTIONIST,
            "branch": self.branch.id,
        }
        payload.update(overrides)
        return payload

    def test_system_admin_can_create_branch_scoped_staff(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.post(
            reverse("api_admin_staff_list_create"),
            self.staff_payload(),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        staff = User.objects.get(username="reception.one")
        self.assertEqual(staff.profile.role, Profile.RECEPTIONIST)
        self.assertEqual(staff.profile.branch, self.branch)
        self.assertTrue(staff.check_password("Strong-Staff-Pass-482!"))
        self.assertFalse(staff.is_staff)
        self.assertFalse(staff.is_superuser)

    def test_customer_cannot_list_or_create_staff(self):
        self.client.force_authenticate(user=self.customer)

        list_response = self.client.get(reverse("api_admin_staff_list_create"))
        create_response = self.client.post(
            reverse("api_admin_staff_list_create"),
            self.staff_payload(),
            format="json",
        )

        self.assertEqual(list_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(create_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(User.objects.filter(username="reception.one").exists())

    def test_branch_scoped_role_requires_active_branch(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.post(
            reverse("api_admin_staff_list_create"),
            self.staff_payload(branch=None),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("branch", response.data)

    def test_system_admin_account_must_be_branchless(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.post(
            reverse("api_admin_staff_list_create"),
            self.staff_payload(
                username="second.admin",
                role=Profile.SYSTEM_ADMIN,
                branch=self.branch.id,
            ),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("branch", response.data)

    def test_system_admin_can_update_staff_role_and_branch_together(self):
        staff = self.create_account(
            username="receptionist",
            role=Profile.RECEPTIONIST,
            branch=self.branch,
        )
        self.client.force_authenticate(user=self.admin)

        response = self.client.patch(
            reverse("api_admin_staff_detail", kwargs={"pk": staff.pk}),
            {
                "role": Profile.SYSTEM_ADMIN,
                "branch": None,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        staff.refresh_from_db()
        self.assertEqual(staff.profile.role, Profile.SYSTEM_ADMIN)
        self.assertIsNone(staff.profile.branch)

    def test_staff_activation_endpoint_soft_deactivates_account(self):
        staff = self.create_account(
            username="counterstaff",
            role=Profile.COUNTER_STAFF,
            branch=self.branch,
        )
        self.client.force_authenticate(user=self.admin)

        response = self.client.patch(
            reverse("api_admin_staff_activation", kwargs={"pk": staff.pk}),
            {"is_active": False},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        staff.refresh_from_db()
        self.assertFalse(staff.is_active)
        self.assertTrue(Profile.objects.filter(user=staff).exists())

    def test_system_admin_cannot_deactivate_self(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.patch(
            reverse("api_admin_staff_activation", kwargs={"pk": self.admin.pk}),
            {"is_active": False},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)

    def test_staff_endpoint_does_not_manage_customer_accounts(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.get(
            reverse("api_admin_staff_detail", kwargs={"pk": self.customer.pk})
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
