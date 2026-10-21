"""Named fakes for the accounts tests (CLAUDE.md §10: no inline stubs for external I/O)."""

from uuid import UUID

from core.domain.exceptions import InvalidPasswordError
from features.accounts.models.profile import Profile
from features.accounts.models.user import User
from features.accounts.repositories.user_repository import UserRepositoryImpl
from features.accounts.services.profile_service import ProfileService


def unsaved_user(username: str = "ana", password: str | None = "secret1") -> User:
    """A user that never touches the database. ``password=None`` plays a Google-only account.

    >>> unsaved_user(password=None).has_usable_password()
    False
    """
    user = User(username=username, email=f"{username}@example.com")
    if password is None:
        user.set_unusable_password()
    else:
        user.set_password(password)
    return user


class RecordingUserRepository(UserRepositoryImpl):
    """Records the two writes account self-service makes instead of running them."""

    def __init__(self) -> None:
        self.passwords: list[tuple[User, str]] = []
        self.deleted: list[User] = []

    def set_password(self, user: User, raw_password: str) -> None:
        user.set_password(raw_password)
        self.passwords.append((user, raw_password))

    def delete(self, user: User) -> None:
        self.deleted.append(user)


class FakeRefreshTokenRepository:
    """Records whose tokens were revoked; pretends each user held ``held`` live tokens."""

    def __init__(self, held: int = 2) -> None:
        self.held = held
        self.revoked: list[UUID] = []

    def revoke_all(self, user_id: UUID) -> int:
        self.revoked.append(user_id)
        return self.held


class FakeGoogleAccountResolver:
    """Stands in for ``GoogleAuthService.resolve_existing_account``: answers every token with
    ``account``, or raises ``error``. Records the tokens it was given."""

    def __init__(self, account: User | None = None, error: Exception | None = None) -> None:
        self.account = account
        self.error = error
        self.tokens: list[str] = []

    def resolve_existing_account(self, token: str) -> User | None:
        self.tokens.append(token)
        if self.error is not None:
            raise self.error
        return self.account


class RecordingPasswordCheck:
    """A ``PasswordCheck`` accepting only ``correct``; records every password it was asked."""

    def __init__(self, correct: str = "secret1") -> None:
        self.correct = correct
        self.asked: list[str] = []

    def __call__(self, raw: str) -> None:
        self.asked.append(raw)
        if raw != self.correct:
            raise InvalidPasswordError()


class RecordingProfileService(ProfileService):
    """The real ``ProfileService``, recording the fields of every ``update_profile`` call, so
    a test can tell that a write went through the service and not around it."""

    def __init__(self, inner: ProfileService) -> None:
        super().__init__(profile_repository=inner._profile_repo)
        self.updates: list[dict[str, object]] = []

    def update_profile(self, user: User, **fields: object) -> Profile:
        self.updates.append(fields)
        return super().update_profile(user, **fields)


class FakeHttpResponse:
    """The two attributes of ``requests.Response`` that ``HttpAvatarDownloader`` reads."""

    def __init__(self, status_code: int, content: bytes = b"") -> None:
        self.status_code = status_code
        self.content = content


class FakeAvatarDownloader:
    """Stands in for ``HttpAvatarDownloader``: answers every URL with ``content`` and
    records the URLs it was asked for. ``content=None`` plays a failed download."""

    def __init__(self, content: bytes | None = None) -> None:
        self.content = content
        self.requested_urls: list[str] = []

    def download(self, url: str) -> bytes | None:
        self.requested_urls.append(url)
        return self.content
