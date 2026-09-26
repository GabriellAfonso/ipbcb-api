"""MemberPhotoService ordering and cleanup (research R-05), with named fakes."""

from collections.abc import Callable
from contextlib import AbstractContextManager
from uuid import uuid4

import pytest

from core.domain.exceptions import MemberNotFoundError, ValidationError
from features.members.dtos import MemberFieldChange
from features.members.services.member_photo_service import MemberPhotoService
from features.members.tests.fakes import (
    FakeMemberChangeLogRepository,
    FakeMemberPhotoStorage,
    FakeMemberRosterRepository,
)
from features.members.tests.images import fake_image_upload, image_upload

CaptureOnCommit = Callable[..., AbstractContextManager[list[Callable[[], object]]]]
EDITOR = uuid4()


class Harness:
    def __init__(self) -> None:
        self.roster = FakeMemberRosterRepository()
        self.change_log = FakeMemberChangeLogRepository()
        self.storage = FakeMemberPhotoStorage()
        self.service = MemberPhotoService(self.roster, self.change_log, self.storage)
        self.member_id = self.roster.add("Ana").id

    def give_photo(self, name: str = "members/old.jpg") -> str:
        self.storage.files[name] = b"old"
        self.roster.set_photo_name(self.member_id, name)
        return name


@pytest.fixture
def h() -> Harness:
    return Harness()


@pytest.mark.django_db
class TestReplacePhoto:
    def test_invalid_image_touches_nothing(self, h: Harness) -> None:
        old = h.give_photo()

        with pytest.raises(ValidationError):
            h.service.replace_photo(h.member_id, fake_image_upload(), EDITOR)

        assert h.storage.files.keys() == {old}
        assert h.roster.get_photo_name(h.member_id) == old
        assert h.change_log.calls == []

    def test_replaces_and_deletes_old_only_on_commit(
        self, h: Harness, django_capture_on_commit_callbacks: CaptureOnCommit
    ) -> None:
        old = h.give_photo()

        with django_capture_on_commit_callbacks() as callbacks:
            path = h.service.replace_photo(h.member_id, image_upload("PNG"), EDITOR)
            assert old not in h.storage.deleted

        new_name = h.roster.get_photo_name(h.member_id)
        assert new_name is not None and new_name.endswith(".png")
        assert path is not None and path.endswith(new_name)
        assert h.change_log.changes == [
            MemberFieldChange(field="photo", old_value=None, new_value="photo changed")
        ]
        for callback in callbacks:
            callback()
        assert h.storage.deleted == [old]

    def test_history_failure_removes_new_file_and_keeps_old(
        self, h: Harness, django_capture_on_commit_callbacks: CaptureOnCommit
    ) -> None:
        old = h.give_photo()
        h.change_log.fail_on_add = True

        with django_capture_on_commit_callbacks() as callbacks:
            with pytest.raises(RuntimeError):
                h.service.replace_photo(h.member_id, image_upload(), EDITOR)

        assert callbacks == []
        # The row rollback is the database's job, covered by the API tests; the fake has none.
        assert h.storage.files.keys() == {old}
        assert len(h.storage.deleted) == 1 and h.storage.deleted[0] != old

    def test_first_photo_schedules_no_deletion(
        self, h: Harness, django_capture_on_commit_callbacks: CaptureOnCommit
    ) -> None:
        with django_capture_on_commit_callbacks() as callbacks:
            h.service.replace_photo(h.member_id, image_upload(), EDITOR)

        assert callbacks == []

    def test_unknown_member_raises(self, h: Harness) -> None:
        with pytest.raises(MemberNotFoundError):
            h.service.replace_photo(999, image_upload(), EDITOR)
        assert h.storage.files == {}


@pytest.mark.django_db
class TestRemovePhoto:
    def test_removes_with_marker_and_deletes_on_commit(
        self, h: Harness, django_capture_on_commit_callbacks: CaptureOnCommit
    ) -> None:
        old = h.give_photo()

        with django_capture_on_commit_callbacks(execute=True):
            h.service.remove_photo(h.member_id, EDITOR)

        assert h.roster.get_photo_name(h.member_id) is None
        assert h.change_log.changes == [
            MemberFieldChange(field="photo", old_value=None, new_value="photo removed")
        ]
        assert h.storage.deleted == [old]

    def test_without_photo_does_nothing(self, h: Harness) -> None:
        h.service.remove_photo(h.member_id, EDITOR)

        assert h.change_log.calls == []
        assert h.storage.deleted == []

    def test_unknown_member_raises(self, h: Harness) -> None:
        with pytest.raises(MemberNotFoundError):
            h.service.remove_photo(999, EDITOR)
