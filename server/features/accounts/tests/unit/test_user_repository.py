import pytest
from django.db import IntegrityError

from core.domain.exceptions import GoogleUserCreationError
from features.accounts.models.user import User
from features.accounts.repositories.user_repository import UserRepositoryImpl
from core.application.dtos.auth_dtos import RegisterDTO


@pytest.fixture
def repo() -> UserRepositoryImpl:
    return UserRepositoryImpl()


@pytest.fixture
def sample_dto() -> RegisterDTO:
    return RegisterDTO(
        username="repouser",
        password="securepass123",
        first_name="Repo",
        last_name="User",
    )


@pytest.mark.django_db
def test_create_returns_user_with_correct_data(
    repo: UserRepositoryImpl, sample_dto: RegisterDTO
) -> None:
    user = repo.create(sample_dto)
    assert isinstance(user, User)
    assert user.username == "repouser"
    assert user.first_name == "Repo"
    assert user.last_name == "User"
    assert user.check_password("securepass123")


@pytest.mark.django_db
def test_get_by_id_returns_user(repo: UserRepositoryImpl, sample_dto: RegisterDTO) -> None:
    created = repo.create(sample_dto)
    found = repo.get_by_id(created.id)
    assert found is not None
    assert found.id == created.id


@pytest.mark.django_db
def test_get_by_id_returns_none_for_unknown(repo: UserRepositoryImpl) -> None:
    import uuid

    assert repo.get_by_id(uuid.uuid4()) is None


@pytest.mark.django_db
def test_get_by_username_returns_user(repo: UserRepositoryImpl, sample_dto: RegisterDTO) -> None:
    repo.create(sample_dto)
    found = repo.get_by_username("repouser")
    assert found is not None
    assert found.username == "repouser"


@pytest.mark.django_db
def test_get_by_username_returns_none_for_unknown(repo: UserRepositoryImpl) -> None:
    assert repo.get_by_username("nonexistent") is None


@pytest.mark.django_db
def test_get_by_email_returns_user(repo: UserRepositoryImpl, sample_dto: RegisterDTO) -> None:
    user = repo.create(sample_dto)
    user.email = "repo@test.com"
    user.save(update_fields=["email"])
    found = repo.get_by_email("repo@test.com")
    assert found is not None
    assert found.id == user.id


@pytest.mark.django_db
def test_get_by_email_returns_none_for_unknown(repo: UserRepositoryImpl) -> None:
    assert repo.get_by_email("nobody@test.com") is None


@pytest.mark.django_db
def test_username_exists_true(repo: UserRepositoryImpl, sample_dto: RegisterDTO) -> None:
    repo.create(sample_dto)
    assert repo.username_exists("repouser") is True


@pytest.mark.django_db
def test_username_exists_false(repo: UserRepositoryImpl) -> None:
    assert repo.username_exists("nonexistent") is False


@pytest.mark.django_db
def test_generate_unique_username_no_collision(repo: UserRepositoryImpl) -> None:
    assert repo.generate_unique_username("newuser") == "newuser"


@pytest.mark.django_db
def test_generate_unique_username_with_collision(
    repo: UserRepositoryImpl, sample_dto: RegisterDTO
) -> None:
    repo.create(sample_dto)
    # "repouser" exists, should get "repouser1"
    assert repo.generate_unique_username("repouser") == "repouser1"


@pytest.mark.django_db
def test_create_google_user(repo: UserRepositoryImpl) -> None:
    user = repo.create_google_user(
        email="google@test.com",
        username="googleuser",
        first_name="Google",
        last_name="User",
    )
    assert user.email == "google@test.com"
    assert user.username == "googleuser"
    assert user.first_name == "Google"
    assert user.last_name == "User"
    assert user.has_usable_password() is False


@pytest.mark.django_db
def test_create_google_user_clash_raises_domain_error_chained(
    repo: UserRepositoryImpl, sample_dto: RegisterDTO
) -> None:
    repo.create(sample_dto)  # takes the username "repouser"

    with pytest.raises(GoogleUserCreationError) as caught:
        repo.create_google_user(
            email="clash@test.com", username="repouser", first_name="A", last_name="B"
        )

    assert isinstance(caught.value.__cause__, IntegrityError)
    assert not User.objects.filter(email="clash@test.com").exists()
