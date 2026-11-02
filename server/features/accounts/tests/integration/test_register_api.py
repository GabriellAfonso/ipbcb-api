import pytest
from django.core import mail
from rest_framework.test import APIClient
from features.accounts.models.profile import Profile
from features.accounts.models.user import User

REGISTER_URL = "/api/auth/register/"

VALID_PAYLOAD = {
    "username": "newuser",
    "first_name": "New",
    "last_name": "User",
    "password": "securepass",
    "password_confirm": "securepass",
    "recovery_email": "newuser@example.com",
}


@pytest.mark.django_db
def test_register_success_returns_201_with_tokens() -> None:
    client = APIClient()
    response = client.post(REGISTER_URL, VALID_PAYLOAD, format="json")
    assert response.status_code == 201
    assert "access" in response.data
    assert "refresh" in response.data


@pytest.mark.django_db
def test_register_creates_user_in_db() -> None:
    client = APIClient()
    client.post(REGISTER_URL, VALID_PAYLOAD, format="json")
    assert User.objects.filter(username="newuser").exists()


@pytest.mark.django_db
def test_register_creates_profile_via_signal() -> None:
    client = APIClient()
    client.post(REGISTER_URL, VALID_PAYLOAD, format="json")
    user = User.objects.get(username="newuser")
    assert Profile.objects.filter(user=user).exists()


@pytest.mark.django_db
def test_register_duplicate_username_returns_400() -> None:
    User.objects.create_user(username="newuser", password="pass123")
    client = APIClient()
    response = client.post(REGISTER_URL, VALID_PAYLOAD, format="json")
    assert response.status_code == 400


@pytest.mark.django_db
def test_register_passwords_mismatch_returns_400() -> None:
    client = APIClient()
    payload = {**VALID_PAYLOAD, "password_confirm": "wrongpass"}
    response = client.post(REGISTER_URL, payload, format="json")
    assert response.status_code == 400


@pytest.mark.django_db
def test_register_missing_fields_returns_400() -> None:
    client = APIClient()
    response = client.post(REGISTER_URL, {"username": "incomplete"}, format="json")
    assert response.status_code == 400


@pytest.mark.django_db
def test_register_username_is_case_insensitive() -> None:
    client = APIClient()
    payload = {**VALID_PAYLOAD, "username": "  NewUser  "}
    client.post(REGISTER_URL, payload, format="json")
    assert User.objects.filter(username="newuser").exists()


@pytest.mark.django_db
@pytest.mark.parametrize("username", ["a/b/c", "..", "foo bar", ".hidden", "joão"])
def test_register_rejects_a_username_unsafe_as_a_directory_name(username: str) -> None:
    """The username becomes a folder under MEDIA_ROOT, so the charset is restricted."""
    client = APIClient()

    response = client.post(REGISTER_URL, {**VALID_PAYLOAD, "username": username}, format="json")

    assert response.status_code == 400
    assert "username" in response.data["field_errors"]
    assert not User.objects.filter(username=username).exists()


@pytest.mark.django_db
def test_register_stores_the_recovery_email_normalised_and_sends_nothing() -> None:
    body = {**VALID_PAYLOAD, "recovery_email": "  NewUser@Example.COM "}

    assert APIClient().post(REGISTER_URL, body, format="json").status_code == 201

    user = User.objects.get(username="newuser")
    assert user.profile.recovery_email == "newuser@example.com"
    assert user.profile.recovery_email_confirmed_at is None
    assert mail.outbox == []


@pytest.mark.django_db
def test_register_never_writes_user_email() -> None:
    APIClient().post(REGISTER_URL, VALID_PAYLOAD, format="json")

    assert User.objects.get(username="newuser").email == ""


@pytest.mark.django_db
def test_register_without_recovery_email_is_refused() -> None:
    body = {k: v for k, v in VALID_PAYLOAD.items() if k != "recovery_email"}

    response = APIClient().post(REGISTER_URL, body, format="json")

    assert response.status_code == 400
    assert response.data["field_errors"]["recovery_email"] == ["Este campo é obrigatório."]
    assert not User.objects.filter(username="newuser").exists()


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("value", "message"),
    [
        ("", "Este campo não pode ficar em branco."),
        ("not-an-email", "Informe um e-mail válido."),
    ],
)
def test_register_with_invalid_recovery_email_is_refused(value: str, message: str) -> None:
    body = {**VALID_PAYLOAD, "recovery_email": value}

    response = APIClient().post(REGISTER_URL, body, format="json")

    assert response.status_code == 400
    assert response.data["field_errors"]["recovery_email"] == [message]


@pytest.mark.django_db
def test_register_accepts_an_address_another_account_uses() -> None:
    APIClient().post(REGISTER_URL, VALID_PAYLOAD, format="json")
    body = {**VALID_PAYLOAD, "username": "otheruser"}

    assert APIClient().post(REGISTER_URL, body, format="json").status_code == 201
