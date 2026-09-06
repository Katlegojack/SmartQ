import json
from datetime import date, time
from pathlib import Path

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from accounts.models import Profile
from branches.models import Branch
from counters.models import Counter
from queues.models import QueueTicket


class Day57SessionCounterStaffingTests(TestCase):
    """Protect live auth transitions and the complete branch counter staffing path."""

    PASSWORD = "SafePassword123!"

    def repo_text(self, path):
        return (Path(__file__).resolve().parents[1] / path).read_text(encoding="utf-8")

    def make_user(self, username, role, branch=None):
        user = User.objects.create_user(
            username=username,
            password=self.PASSWORD,
            first_name=username.title(),
        )
        Profile.objects.create(
            user=user,
            date_of_birth=date(1990, 1, 1),
            gender=Profile.OTHER,
            role=role,
            branch=branch,
        )
        return user

    def setUp(self):
        self.branch = Branch.objects.create(
            branch_code="D57BARBER",
            name="Day 57 Barber Shop",
            address="57 Counter Street",
            city="Pretoria",
            opening_time=time(8, 0),
            closing_time=time(18, 0),
            is_active=True,
        )
        self.admin = self.make_user("day57_admin", Profile.SYSTEM_ADMIN)
        self.manager = self.make_user("messi", Profile.BRANCH_MANAGER, self.branch)
        self.staff = self.make_user("day57_barber", Profile.COUNTER_STAFF, self.branch)

    def test_admin_can_create_counter_then_manager_assigns_staff_in_separate_session(self):
        admin_browser = Client()
        admin_browser.force_login(self.admin)
        create = admin_browser.post(
            reverse("api_counter_admin_list_create"),
            data=json.dumps(
                {
                    "branch": self.branch.id,
                    "counter_number": "1",
                    "queue_type": QueueTicket.GENERAL,
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(create.status_code, 201)
        counter_id = create.json()["id"]
        self.assertEqual(create.json()["status"], Counter.CLOSED)
        self.assertIsNone(create.json()["assigned_staff"])

        # Manager and Counter Staff intentionally use different browser clients,
        # matching separate real devices/profiles rather than sharing one cookie.
        manager_browser = Client()
        manager_browser.force_login(self.manager)
        assignment = manager_browser.post(
            reverse("api_counter_assign_staff", args=[counter_id]),
            data=json.dumps({"staff_user_id": self.staff.id}),
            content_type="application/json",
        )
        self.assertEqual(assignment.status_code, 200)
        self.assertEqual(assignment.json()["assigned_staff"], self.staff.id)

        staff_browser = Client()
        staff_browser.force_login(self.staff)
        my_counter = staff_browser.get(reverse("api_my_assigned_counter"))
        self.assertEqual(my_counter.status_code, 200)
        self.assertEqual(my_counter.json()["id"], counter_id)

        opened = manager_browser.post(reverse("api_counter_open", args=[counter_id]))
        self.assertEqual(opened.status_code, 200)
        self.assertEqual(opened.json()["status"], Counter.OPEN)

        closed = manager_browser.post(reverse("api_counter_close", args=[counter_id]))
        self.assertEqual(closed.status_code, 200)
        self.assertEqual(closed.json()["status"], Counter.CLOSED)

    def test_counter_configuration_is_unique_and_only_changes_while_closed(self):
        counter = Counter.objects.create(
            branch=self.branch,
            counter_number="1",
            queue_type=QueueTicket.GENERAL,
            status=Counter.OPEN,
            assigned_staff=self.staff,
        )
        browser = Client()
        browser.force_login(self.admin)

        open_update = browser.patch(
            reverse("api_counter_admin_detail", args=[counter.id]),
            data=json.dumps({"queue_type": QueueTicket.PRIORITY}),
            content_type="application/json",
        )
        self.assertEqual(open_update.status_code, 409)
        self.assertIn("Close this counter", open_update.json()["detail"])

        counter.status = Counter.CLOSED
        counter.save(update_fields=["status"])
        closed_update = browser.patch(
            reverse("api_counter_admin_detail", args=[counter.id]),
            data=json.dumps({"counter_number": "Front Desk", "queue_type": QueueTicket.PRIORITY}),
            content_type="application/json",
        )
        self.assertEqual(closed_update.status_code, 200)
        self.assertEqual(closed_update.json()["counter_number"], "Front Desk")
        self.assertEqual(closed_update.json()["queue_type"], QueueTicket.PRIORITY)

        duplicate = browser.post(
            reverse("api_counter_admin_list_create"),
            data=json.dumps(
                {
                    "branch": self.branch.id,
                    "counter_number": "front desk",
                    "queue_type": QueueTicket.GENERAL,
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(duplicate.status_code, 400)
        self.assertIn("counter_number", duplicate.json())

    def test_manager_frontend_has_complete_staffing_controls_and_clear_empty_states(self):
        manager = self.repo_text("frontend/src/pages/ManagerPage.tsx")
        counter_admin = self.repo_text("frontend/src/pages/CounterAdminPage.tsx")
        components = self.repo_text("frontend/src/components.tsx")
        app = self.repo_text("frontend/src/App.tsx")

        for contract in [
            "No counters configured",
            "No Counter Staff in this branch",
            "Close counter to change staff.",
            '`counters/${counter.id}/close/`',
            "Assign Counter Staff to counter",
            "refetchInterval: 5_000",
        ]:
            self.assertIn(contract, manager)

        for contract in [
            '"/api/v1/counters/admin/"',
            "Create counter",
            "Update counter",
            "The Branch Manager can now assign Counter Staff.",
        ]:
            self.assertIn(contract, counter_admin)

        self.assertIn('["Counters", "/app/admin/counters/"]', components)
        self.assertIn('path="/app/admin/counters/"', app)

    def test_auth_runtime_hard_redirects_to_server_login_and_guards_session_races(self):
        react_api = self.repo_text("frontend/src/api.ts")
        auth = self.repo_text("frontend/src/auth.ts")
        legacy_api = self.repo_text("static/js/api/client.js")
        app = self.repo_text("frontend/src/App.tsx")
        components = self.repo_text("frontend/src/components.tsx")

        for contract in [
            "readCookie(CSRF_COOKIE_NAME)",
            "markAuthTransition",
            "confirmAuthenticatedSession",
            "requestEpoch",
            "suppressSessionExpiry",
        ]:
            self.assertIn(contract, react_api)

        self.assertGreaterEqual(auth.count("markAuthTransition();"), 4)
        self.assertIn("readCookie(CSRF_COOKIE_NAME)", legacy_api)
        self.assertIn("window.location.replace(`${loginPath}?next=${next}`)", app)
        self.assertIn('<Route path="/staff-login/" element={<ServerRedirect', app)
        self.assertIn("export function ServerRedirect", components)

    def test_auth_and_frontend_entry_responses_are_non_cacheable_and_versioned(self):
        login = self.client.get(reverse("frontend_staff_login"))
        self.assertEqual(login.status_code, 200)
        cache_control = login.headers.get("Cache-Control", "")
        self.assertIn("no-cache", cache_control)
        self.assertContains(login, "/static/js/pages/login.js?v=")
        self.assertNotContains(login, "Your session ended")

        manager_shell = self.client.get(reverse("frontend_manager_workspace"))
        self.assertEqual(manager_shell.status_code, 200)
        self.assertIn("no-cache", manager_shell.headers.get("Cache-Control", ""))
        self.assertContains(manager_shell, "/static/react/app.js?v=")
        self.assertContains(manager_shell, "/static/react/app.css?v=")

        self.client.force_login(self.manager)
        me = self.client.get(reverse("api_current_account"))
        self.assertEqual(me.status_code, 200)
        self.assertIn("no-cache", me.headers.get("Cache-Control", ""))
