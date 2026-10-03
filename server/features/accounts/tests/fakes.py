"""Named fakes for the accounts tests (CLAUDE.md §10: no inline stubs for external I/O)."""

from features.accounts.models.profile import Profile
from features.accounts.models.user import User
from features.accounts.services.profile_service import ProfileService


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
