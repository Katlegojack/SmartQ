from django.contrib.staticfiles import finders
from django.test import TestCase
from django.urls import reverse


class FrontendFoundationTests(TestCase):
    def test_frontend_home_renders_successfully(self):
        response = self.client.get(reverse("frontend_home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "SMART Q")
        self.assertContains(response, "Where Time Meets Priority")
        self.assertContains(response, "Vision")
        self.assertContains(response, "Mission")
        self.assertContains(response, "Give people their time back")
        self.assertContains(response, "Make waiting predictable, transparent and fair")
        self.assertContains(response, "Customer sign in")
        self.assertContains(response, "Staff &amp; administration sign in")
        self.assertContains(response, "/staff-login/")

    def test_frontend_home_stays_product_focused(self):
        response = self.client.get(reverse("frontend_home"))
        content = response.content.decode("utf-8")

        for banned in [
            "Queue intelligence platform",
            "Frontend foundation",
            "Backend v1 connected",
            "Dense operational data",
            "Queue status preview",
            "HTML, CSS and JavaScript frontend",
        ]:
            with self.subTest(banned=banned):
                self.assertNotIn(banned, content)

    def test_frontend_home_references_shared_assets(self):
        response = self.client.get(reverse("frontend_home"))

        self.assertContains(response, "/static/css/smartq.css")
        self.assertContains(response, "/static/css/home.css")
        self.assertContains(response, "/static/js/app.js")

    def test_frontend_assets_are_discoverable(self):
        self.assertIsNotNone(finders.find("css/smartq.css"))
        self.assertIsNotNone(finders.find("css/home.css"))
        self.assertIsNotNone(finders.find("js/app.js"))
