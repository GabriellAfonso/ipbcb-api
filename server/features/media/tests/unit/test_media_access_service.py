import logging

import pytest

from core.domain.exceptions import (
    DomainError,
    MediaAccessDeniedError,
    MediaFileNotFoundError,
    MediaFolderNotRuledError,
    MediaPathRejectedError,
)
from features.media.dtos.media_dtos import MediaViewer
from features.media.services.media_access_service import MediaAccessService
from features.media.tests.fakes import FAKE_MEDIA_ROOT, FakeMediaFileRepository

GALLERY_FILE = "gallery/retiro-2025/IMG_0042.jpg"
PROFILE_FILE = "profiles/ana.paula/6f1c2d.png"

MEMBER = MediaViewer(is_member=True, is_leader=False)
NON_MEMBER = MediaViewer(is_member=False, is_leader=False)
BOTH = MediaViewer(is_member=True, is_leader=True)
NON_MEMBER_OWNER = MediaViewer(is_member=False, is_leader=False, own_profile_folder="ana.paula")


def _service(repository: FakeMediaFileRepository) -> MediaAccessService:
    return MediaAccessService(repository=repository)


def _decision_records(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    return [r for r in caplog.records if r.getMessage() == "media_access"]


class TestAllowed:
    @pytest.mark.parametrize(
        "path,content_type", [(GALLERY_FILE, "image/jpeg"), (PROFILE_FILE, "image/png")]
    )
    def test_member_gets_media_file(self, path: str, content_type: str) -> None:
        media_file = _service(FakeMediaFileRepository({path: b"x"})).authorize(path, MEMBER)
        assert media_file.relative_path == path
        assert media_file.absolute_path == FAKE_MEDIA_ROOT / path
        assert media_file.content_type == content_type

    def test_open_returns_file_bytes(self) -> None:
        service = _service(FakeMediaFileRepository({GALLERY_FILE: b"bytes"}))
        media_file = service.authorize(GALLERY_FILE, MEMBER)
        assert service.open(media_file).read() == b"bytes"


class TestDenied:
    def test_non_member_is_denied_before_existence_is_checked(self) -> None:
        repository = FakeMediaFileRepository({GALLERY_FILE: b"x"})
        with pytest.raises(MediaAccessDeniedError):
            _service(repository).authorize(GALLERY_FILE, NON_MEMBER)
        assert repository.located == []

    def test_missing_file_is_not_found(self) -> None:
        with pytest.raises(MediaFileNotFoundError):
            _service(FakeMediaFileRepository()).authorize("gallery/a/missing.jpg", MEMBER)

    def test_unruled_folder_is_not_found_even_for_both_flags(self) -> None:
        repository = FakeMediaFileRepository({"reports/2026.pdf": b"x"})
        with pytest.raises(MediaFolderNotRuledError):
            _service(repository).authorize("reports/2026.pdf", BOTH)
        assert repository.located == []

    def test_rejected_path_never_reaches_repository(self) -> None:
        repository = FakeMediaFileRepository()
        with pytest.raises(MediaPathRejectedError):
            _service(repository).authorize("gallery/../x.jpg", MEMBER)
        assert repository.located == []


class TestDecisionLog:
    @pytest.mark.parametrize(
        "path,viewer,outcome,folder",
        [
            (GALLERY_FILE, MEMBER, "allowed", "gallery"),
            (GALLERY_FILE, NON_MEMBER, "forbidden", "gallery"),
            ("gallery/a/missing.jpg", MEMBER, "not_found", "gallery"),
            ("gallery/../secret.jpg", MEMBER, "rejected", None),
        ],
    )
    def test_one_record_with_folder_and_outcome_only(
        self,
        caplog: pytest.LogCaptureFixture,
        path: str,
        viewer: MediaViewer,
        outcome: str,
        folder: str | None,
    ) -> None:
        service = _service(FakeMediaFileRepository({GALLERY_FILE: b"x"}))
        with caplog.at_level(logging.INFO):
            try:
                service.authorize(path, viewer)
            except DomainError:
                pass  # the logged outcome, not the exception, is under test here
        [record] = _decision_records(caplog)
        assert getattr(record, "outcome") == outcome
        assert getattr(record, "folder") == folder
        assert path.rsplit("/", 1)[-1] not in str(record.__dict__)


class TestLeaderFolder:
    MEMBERS_FILE = "members/ana/photo.jpg"

    @pytest.mark.parametrize(
        "viewer",
        [MediaViewer(is_member=False, is_leader=True), MediaViewer(is_member=True, is_leader=True)],
    )
    def test_leader_gets_media_file(self, viewer: MediaViewer) -> None:
        repository = FakeMediaFileRepository({self.MEMBERS_FILE: b"x"})
        assert _service(repository).authorize(self.MEMBERS_FILE, viewer).relative_path == (
            self.MEMBERS_FILE
        )

    @pytest.mark.parametrize("viewer", [MEMBER, NON_MEMBER])
    def test_non_leader_denied_before_existence_is_checked(self, viewer: MediaViewer) -> None:
        repository = FakeMediaFileRepository({self.MEMBERS_FILE: b"x"})
        with pytest.raises(MediaAccessDeniedError):
            _service(repository).authorize(self.MEMBERS_FILE, viewer)
        assert repository.located == []


def test_unruled_decision_does_not_log_the_folder(caplog: pytest.LogCaptureFixture) -> None:
    # The first segment of an unruled path is attacker-chosen text.
    with caplog.at_level(logging.INFO), pytest.raises(MediaFolderNotRuledError):
        _service(FakeMediaFileRepository()).authorize("reports/2026.pdf", BOTH)
    [record] = _decision_records(caplog)
    assert getattr(record, "outcome") == "unruled"
    assert getattr(record, "folder") is None


class TestProfileOwner:
    def test_non_member_owner_gets_own_photo(self) -> None:
        service = _service(FakeMediaFileRepository({PROFILE_FILE: b"x"}))
        assert service.authorize(PROFILE_FILE, NON_MEMBER_OWNER).relative_path == PROFILE_FILE

    def test_non_member_owner_denied_on_another_users_photo(self) -> None:
        other_photo = "profiles/joao/6f1c2d.png"
        repository = FakeMediaFileRepository({other_photo: b"x"})
        with pytest.raises(MediaAccessDeniedError):
            _service(repository).authorize(other_photo, NON_MEMBER_OWNER)
        assert repository.located == []

    def test_non_member_owner_still_denied_on_gallery(self) -> None:
        with pytest.raises(MediaAccessDeniedError):
            _service(FakeMediaFileRepository({GALLERY_FILE: b"x"})).authorize(
                GALLERY_FILE, NON_MEMBER_OWNER
            )
