"""Leader-only member photo (US4). Files land in a tmp MEDIA_ROOT; on-commit callbacks are
executed so storage cleanup runs as it does after a real commit."""

import re
from collections.abc import Callable
from contextlib import AbstractContextManager
from pathlib import Path

import pytest
from rest_framework.test import APIClient

from conftest import make_admin_client, make_member_client
from features.members.models.member import Member
from features.members.models.member_change_log import MemberChangeLog
from features.members.tests.images import fake_image_upload, image_upload

CaptureOnCommit = Callable[..., AbstractContextManager[list[Callable[[], object]]]]


def photo_url(member_id: int) -> str:
    return f"/api/admin/members/{member_id}/photo/"


def _put(client: APIClient, member_id: int, upload: object) -> object:
    return client.put(photo_url(member_id), {"photo": upload}, format="multipart")


def _stored_files(media_root: Path) -> list[str]:
    folder = media_root / "members"
    return sorted(p.name for p in folder.iterdir()) if folder.exists() else []


@pytest.mark.django_db
class TestAccess:
    def test_anonymous_401(self, media_root: Path) -> None:
        member = Member.objects.create(name="Ana")
        assert APIClient().put(photo_url(member.pk)).status_code == 401

    def test_plain_member_403_and_nothing_stored(self, media_root: Path) -> None:
        member = Member.objects.create(name="Ana")
        client, _ = make_member_client()

        response = client.put(photo_url(member.pk), {"photo": image_upload()}, format="multipart")

        assert response.status_code == 403
        assert _stored_files(media_root) == []

    def test_unknown_member_404(self, media_root: Path) -> None:
        client, _ = make_admin_client()

        response = client.put(photo_url(999), {"photo": image_upload()}, format="multipart")

        assert response.status_code == 404
        assert _stored_files(media_root) == []


@pytest.mark.django_db
class TestUpload:
    def test_missing_field_400(self, media_root: Path) -> None:
        member = Member.objects.create(name="Ana")
        client, _ = make_admin_client()

        response = client.put(photo_url(member.pk), {}, format="multipart")

        assert response.status_code == 400
        assert response.data["error_code"] == "VALIDATION_ERROR"

    def test_upload_stores_random_name_and_writes_marker(
        self, media_root: Path, django_capture_on_commit_callbacks: CaptureOnCommit
    ) -> None:
        member = Member.objects.create(name="Ana Souza")
        client, _ = make_admin_client()

        with django_capture_on_commit_callbacks(execute=True):
            response = client.put(
                photo_url(member.pk), {"photo": image_upload()}, format="multipart"
            )

        assert response.status_code == 200
        assert re.fullmatch(
            r"http://testserver/ipbcb/media/members/[0-9a-f]{32}\.jpg", response.data["photo_url"]
        )
        assert "ana" not in response.data["photo_url"].lower()
        (entry,) = MemberChangeLog.objects.filter(member=member)
        assert (entry.field, entry.old_value, entry.new_value) == ("photo", None, "photo changed")

    def test_replace_removes_old_file(
        self, media_root: Path, django_capture_on_commit_callbacks: CaptureOnCommit
    ) -> None:
        member = Member.objects.create(name="Ana")
        client, _ = make_admin_client()
        with django_capture_on_commit_callbacks(execute=True):
            _put(client, member.pk, image_upload())
        (old_file,) = _stored_files(media_root)

        with django_capture_on_commit_callbacks(execute=True):
            _put(client, member.pk, image_upload("PNG", "b.png"))

        (new_file,) = _stored_files(media_root)
        assert new_file != old_file and new_file.endswith(".png")
        assert MemberChangeLog.objects.filter(member=member, field="photo").count() == 2

    def test_fake_image_rejected_and_current_photo_intact(
        self, media_root: Path, django_capture_on_commit_callbacks: CaptureOnCommit
    ) -> None:
        member = Member.objects.create(name="Ana")
        client, _ = make_admin_client()
        with django_capture_on_commit_callbacks(execute=True):
            _put(client, member.pk, image_upload())
        before = _stored_files(media_root)

        response = client.put(
            photo_url(member.pk), {"photo": fake_image_upload()}, format="multipart"
        )

        assert response.status_code == 400
        assert _stored_files(media_root) == before
        member.refresh_from_db()
        assert member.photo.name == f"members/{before[0]}"


@pytest.mark.django_db
class TestMediaAccess:
    def test_leader_can_read_member_cannot(
        self, media_root: Path, django_capture_on_commit_callbacks: CaptureOnCommit
    ) -> None:
        member = Member.objects.create(name="Ana")
        leader, _ = make_admin_client()
        with django_capture_on_commit_callbacks(execute=True):
            url = leader.put(
                photo_url(member.pk), {"photo": image_upload()}, format="multipart"
            ).data["photo_url"]
        path = url.removeprefix("http://testserver")
        plain_member, _ = make_member_client()

        assert leader.get(path).status_code == 200
        assert plain_member.get(path).status_code == 403


@pytest.mark.django_db
class TestRemove:
    def test_remove_deletes_file_and_writes_marker(
        self, media_root: Path, django_capture_on_commit_callbacks: CaptureOnCommit
    ) -> None:
        member = Member.objects.create(name="Ana")
        client, _ = make_admin_client()
        with django_capture_on_commit_callbacks(execute=True):
            _put(client, member.pk, image_upload())

        with django_capture_on_commit_callbacks(execute=True):
            response = client.delete(photo_url(member.pk))

        assert response.status_code == 204
        assert _stored_files(media_root) == []
        member.refresh_from_db()
        assert not member.photo
        latest = MemberChangeLog.objects.filter(member=member).first()
        assert latest is not None and latest.new_value == "photo removed"

    def test_remove_without_photo_writes_nothing(self, media_root: Path) -> None:
        member = Member.objects.create(name="Ana")
        client, _ = make_admin_client()

        assert client.delete(photo_url(member.pk)).status_code == 204
        assert not MemberChangeLog.objects.exists()

    def test_member_delete_removes_photo_file(
        self, media_root: Path, django_capture_on_commit_callbacks: CaptureOnCommit
    ) -> None:
        member = Member.objects.create(name="Ana")
        client, _ = make_admin_client()
        with django_capture_on_commit_callbacks(execute=True):
            _put(client, member.pk, image_upload())

        with django_capture_on_commit_callbacks(execute=True):
            response = client.delete(f"/api/admin/members/{member.pk}/")

        assert response.status_code == 204
        assert _stored_files(media_root) == []
