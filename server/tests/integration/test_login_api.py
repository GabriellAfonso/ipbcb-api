from django.test import TestCase
from rest_framework.test import APIClient
from django.urls import reverse

from apps.accounts.models.user import User


class LoginAPIIntegrationTest(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.password = "verysecure123"

        self.user = User.objects.create_user(
            username="arimakousei",
            first_name="Arima",
            last_name="Kousei",
            password=self.password,
        )

    def test_login_returns_tokens_with_valid_credentials(self):
        payload = {
            "username": "arimakousei",
            "password": self.password,
        }

        resp = self.client.post("/api/auth/login/",
                                payload, format="json")

        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertIn("access", resp.data)
        self.assertIn("refresh", resp.data)

    def test_login_fails_with_invalid_credentials(self):
        payload = {
            "username": "arimakousei",
            "password": "wrongpassword",
        }

        resp = self.client.post("/api/auth/login/",
                                payload, format="json")

        self.assertEqual(resp.status_code, 401)
        self.assertIn("detail", resp.data)
