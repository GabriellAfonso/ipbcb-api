from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models.user import User


class RegisterAPIIntegrationTest(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_register_endpoint_creates_user_and_returns_tokens(self):
        payload = {
            "username": "charlie",
            "first_name": "Charlie",
            "last_name": "Chaplin",
            "password": "verysecure123",
            "password_confirm": "verysecure123",
        }

        resp = self.client.post("/api/auth/register/",
                                payload, format="json")

        # status + tokens
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertIn("access", resp.data)
        self.assertIn("refresh", resp.data)

        # usuário criado no DB
        self.assertTrue(User.objects.filter(
            username=payload["username"]).exists())
        user = User.objects.get(username=payload["username"])
        self.assertEqual(user.first_name, payload["first_name"])
        self.assertEqual(user.last_name, payload["last_name"])
        self.assertTrue(user.check_password(payload["password"]))
