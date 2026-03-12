from django.test import TestCase
from rest_framework.test import APIClient
from django.urls import reverse

from apps.accounts.models.user import User


class TokenRefreshIntegrationTest(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.password = "verysecure123"

        self.user = User.objects.create_user(
            username="charlie",
            password=self.password,
        )

        # faz login para obter refresh
        login_resp = self.client.post(
            "/api/auth/login/",
            {
                "username": "charlie",
                "password": self.password,
            },
            format="json",
        )

        self.refresh_token = login_resp.data["refresh"]

    def test_refresh_returns_new_access_token(self):
        resp = self.client.post(
            "/api/auth/refresh/",
            {"refresh": self.refresh_token},
            format="json",
        )

        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertIn("access", resp.data)

    def test_refresh_fails_with_invalid_token(self):
        resp = self.client.post(
            "/api/auth/refresh/",
            {"refresh": "invalidtoken"},
            format="json",
        )

        self.assertEqual(resp.status_code, 401)
