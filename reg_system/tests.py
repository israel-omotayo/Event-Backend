from django.test import SimpleTestCase, override_settings
from django.urls import reverse


@override_settings(DEBUG=False, ALLOWED_HOSTS=["api.example.com"])
class HealthCheckTests(SimpleTestCase):
    def test_health_check_works_in_production_settings(self):
        response = self.client.get(reverse("health-check"), HTTP_HOST="api.example.com")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_health_check_accepts_trailing_slash_in_production_settings(self):
        response = self.client.get("/health/", HTTP_HOST="api.example.com")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})
