from django.contrib.staticfiles import finders
from django.test import TestCase
from django.urls import reverse


class FrontendFoundationTests(TestCase):
    def test_frontend_home_renders_successfully(self):
        response = self.client.get(reverse("frontend_home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Smart Q")
        self.assertContains(response, "Queue intelligence platform")
        self.assertContains(response, "Backend v1 connected to the frontend authentication shell")

    def test_frontend_home_references_shared_assets(self):
        response = self.client.get(reverse("frontend_home"))

        self.assertContains(response, "/static/css/smartq.css")
        self.assertContains(response, "/static/js/app.js")

    def test_frontend_assets_are_discoverable(self):
        self.assertIsNotNone(finders.find("css/smartq.css"))
        self.assertIsNotNone(finders.find("js/app.js"))
