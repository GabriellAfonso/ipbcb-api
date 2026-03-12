from django.test import SimpleTestCase

from apps.accounts.serializers.serializers import RegisterSerializer


class RegisterSerializerUnitTest(SimpleTestCase):
    def test_validate_password_mismatch(self):
        data = {
            "username": "alicesilva",
            "first_name": "Alice",
            "last_name": "silva",
            "password": "password1",
            "password_confirm": "password2",
        }
        serializer = RegisterSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("password_confirm", serializer.errors)

    def test_create_dto_and_valid(self):
        data = {
            "username": "daniellima",
            "first_name": "daniel",
            "last_name": "lima",
            "password": "complexpass123",
            "password_confirm": "complexpass123",
        }
        serializer = RegisterSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)

        dto = serializer.create_dto()
        # Só valida os campos do DTO (evita acessar DB)
        self.assertEqual(dto.username, data["username"])
        self.assertEqual(dto.first_name, data["first_name"])
        self.assertEqual(dto.last_name, data["last_name"])
