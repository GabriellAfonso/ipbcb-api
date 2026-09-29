"""Member tags through the API (specs/015-gallery-member-tags US1, US2, US4, US6; contract).

Lives with the gallery tests and builds ``Member`` rows through the ORM of the test database
only: the gallery code under test never imports the members feature.
"""

from typing import Any

import pytest
from django.apps import apps
from rest_framework.test import APIClient

from conftest import make_auth_client, make_member_client, make_user
from features.gallery.models.gallery import Album, Photo
from features.gallery.models.tags import PhotoTag
from features.gallery.tests.integration.helpers import gallery_manager

PICKER = "/api/gallery/taggable-members/"
TAGGED = "/api/gallery/tagged-members/"
BULK = "/api/photos/members/"


def _member_model() -> Any:
    return apps.get_model("members", "Member")


def _put(photo_id: int) -> str:
    return f"/api/photos/{photo_id}/members/"


def _ids(items: object) -> list[int]:
    return [item["id"] for item in items]  # type: ignore[attr-defined]


class Gallery:
    """Album A (photos p1, p2) with sub-album B (photo pb); members Ana, Bruno, Carla, and
    Davi, who is not a valid profile any more."""

    def __init__(self) -> None:
        self.manager: APIClient = gallery_manager()
        self.member: APIClient = make_member_client()[0]
        self.a = Album.objects.create(name="A")
        self.b = Album.objects.create(name="B", parent=self.a)
        self.p1 = Photo.objects.create(album=self.a, name="1.jpg", image="x/1.jpg", position=0)
        self.p2 = Photo.objects.create(album=self.a, name="2.jpg", image="x/2.jpg", position=1)
        self.pb = Photo.objects.create(album=self.b, name="b.jpg", image="x/b.jpg")
        member = _member_model()
        self.carla = member.objects.create(name="Carla")
        self.ana = member.objects.create(name="Ana")
        self.bruno = member.objects.create(name="Bruno")
        self.davi = member.objects.create(name="Davi", is_active=False)

    def tag(self, photo: Photo, *members: Any) -> None:
        PhotoTag.objects.bulk_create([PhotoTag(photo=photo, member=m) for m in members])

    def tags_of(self, photo: Photo) -> set[int]:
        return set(PhotoTag.objects.filter(photo=photo).values_list("member_id", flat=True))


@pytest.mark.django_db
class TestPicker:
    def test_every_member_by_name_inactive_included(self) -> None:
        gallery = Gallery()

        body = gallery.manager.get(PICKER).data

        assert [m["name"] for m in body] == ["Ana", "Bruno", "Carla", "Davi"]

    def test_regression_entries_carry_only_id_and_name(self) -> None:
        body = Gallery().manager.get(PICKER).data

        assert all(set(entry) == {"id", "name"} for entry in body)

    def test_private_and_revalidated(self) -> None:
        gallery = Gallery()
        first = gallery.manager.get(PICKER)

        again = gallery.manager.get(PICKER, HTTP_IF_NONE_MATCH=first["ETag"])

        assert "private" in first["Cache-Control"] and "no-store" in first["Cache-Control"]
        assert again.status_code == 304


@pytest.mark.django_db
class TestReplace:
    def test_tags_two_members_and_every_reader_sees_them(self) -> None:
        gallery = Gallery()

        response = gallery.manager.put(
            _put(gallery.p1.pk), {"member_ids": [gallery.bruno.pk, gallery.ana.pk]}, format="json"
        )

        assert response.status_code == 200
        assert response.data["members"] == [
            {"id": gallery.ana.pk, "name": "Ana"},
            {"id": gallery.bruno.pk, "name": "Bruno"},
        ]
        listed = {p["id"]: p for p in gallery.member.get("/api/photos/").data}
        in_album = {
            p["id"]: p for p in gallery.member.get(f"/api/albums/{gallery.a.pk}/photos/").data
        }
        assert listed[gallery.p1.pk]["members"] == response.data["members"]
        assert in_album[gallery.p1.pk]["members"] == response.data["members"]
        assert listed[gallery.p2.pk]["members"] == []

    def test_replaces_the_whole_set(self) -> None:
        gallery = Gallery()
        gallery.tag(gallery.p1, gallery.ana, gallery.bruno)

        gallery.manager.put(
            _put(gallery.p1.pk), {"member_ids": [gallery.bruno.pk, gallery.carla.pk]}, format="json"
        )

        assert gallery.tags_of(gallery.p1) == {gallery.bruno.pk, gallery.carla.pk}

    def test_empty_list_clears(self) -> None:
        gallery = Gallery()
        gallery.tag(gallery.p1, gallery.ana)

        response = gallery.manager.put(_put(gallery.p1.pk), {"member_ids": []}, format="json")

        assert response.data["members"] == []
        assert gallery.tags_of(gallery.p1) == set()

    def test_repeated_ids_count_once(self) -> None:
        gallery = Gallery()
        ids = [gallery.ana.pk, gallery.ana.pk]

        response = gallery.manager.put(_put(gallery.p1.pk), {"member_ids": ids}, format="json")

        assert _ids(response.data["members"]) == [gallery.ana.pk]

    def test_inactive_member_is_tagged_and_shown(self) -> None:
        gallery = Gallery()

        gallery.manager.put(_put(gallery.p1.pk), {"member_ids": [gallery.davi.pk]}, format="json")

        photo = gallery.member.get(f"/api/albums/{gallery.a.pk}/photos/").data[0]
        assert photo["members"] == [{"id": gallery.davi.pk, "name": "Davi"}]

    def test_records_who_tagged_but_never_shows_it(self) -> None:
        gallery = Gallery()

        response = gallery.manager.put(
            _put(gallery.p1.pk), {"member_ids": [gallery.ana.pk]}, format="json"
        )

        assert PhotoTag.objects.get(photo=gallery.p1).tagged_by is not None
        assert set(response.data["members"][0]) == {"id", "name"}

    def test_unknown_member_is_404_and_nothing_changes(self) -> None:
        gallery = Gallery()
        gallery.tag(gallery.p1, gallery.ana)

        response = gallery.manager.put(
            _put(gallery.p1.pk), {"member_ids": [gallery.bruno.pk, 999_999]}, format="json"
        )

        assert response.status_code == 404
        assert response.data["missing_member_ids"] == [999_999]
        assert gallery.tags_of(gallery.p1) == {gallery.ana.pk}

    def test_trashed_photo_is_404(self) -> None:
        gallery = Gallery()
        gallery.manager.delete(f"/api/photos/{gallery.p1.pk}/")

        response = gallery.manager.put(
            _put(gallery.p1.pk), {"member_ids": [gallery.ana.pk]}, format="json"
        )

        assert response.status_code == 404
        assert response.data["photo_id"] == gallery.p1.pk

    @pytest.mark.parametrize(
        "body", [{}, {"member_ids": "1"}, {"member_ids": ["a"]}, {"member_ids": [], "x": 1}]
    )
    def test_malformed_body_is_400(self, body: dict[str, object]) -> None:
        gallery = Gallery()

        assert gallery.manager.put(_put(gallery.p1.pk), body, format="json").status_code == 400


@pytest.mark.django_db
class TestFilter:
    def _tagged(self) -> Gallery:
        gallery = Gallery()
        gallery.tag(gallery.p1, gallery.ana, gallery.bruno)
        gallery.tag(gallery.p2, gallery.ana)
        gallery.tag(gallery.pb, gallery.ana, gallery.bruno)
        return gallery

    def test_regression_two_members_means_both(self) -> None:
        gallery = self._tagged()
        query = {"member_id": [gallery.ana.pk, gallery.bruno.pk]}

        body = gallery.member.get("/api/photos/", query).data

        assert _ids(body) == [gallery.p1.pk, gallery.pb.pk]

    def test_regression_album_filter_keeps_only_direct_photos(self) -> None:
        gallery = self._tagged()
        query = {"member_id": [gallery.ana.pk, gallery.bruno.pk]}

        body = gallery.member.get(f"/api/albums/{gallery.a.pk}/photos/", query).data

        assert _ids(body) == [gallery.p1.pk]

    def test_one_member_in_the_usual_order(self) -> None:
        gallery = self._tagged()

        body = gallery.member.get("/api/photos/", {"member_id": gallery.ana.pk}).data

        assert _ids(body) == [gallery.p1.pk, gallery.p2.pk, gallery.pb.pk]

    def test_repeated_value_counts_once(self) -> None:
        gallery = self._tagged()
        query = {"member_id": [gallery.bruno.pk, gallery.bruno.pk]}

        assert _ids(gallery.member.get("/api/photos/", query).data) == [
            gallery.p1.pk,
            gallery.pb.pk,
        ]

    def test_unknown_member_gives_an_empty_list(self) -> None:
        gallery = self._tagged()

        response = gallery.member.get("/api/photos/", {"member_id": 999_999})

        assert (response.status_code, response.data) == (200, [])

    @pytest.mark.parametrize("bad", ["abc", "1.5", ""])
    def test_value_that_is_not_an_integer_is_400(self, bad: str) -> None:
        gallery = self._tagged()

        response = gallery.member.get("/api/photos/", {"member_id": [gallery.ana.pk, bad]})

        assert response.status_code == 400
        assert repr(bad) in str(response.data["detail"])

    def test_regression_trashed_photo_hidden_and_back_on_restore(self) -> None:
        gallery = self._tagged()
        gallery.manager.delete(f"/api/photos/{gallery.p2.pk}/")

        filtered = gallery.member.get("/api/photos/", {"member_id": gallery.ana.pk}).data
        counts = {m["id"]: m["photo_count"] for m in gallery.member.get(TAGGED).data}
        gallery.manager.post(f"/api/gallery/trash/photos/{gallery.p2.pk}/restore/")
        restored = gallery.member.get(f"/api/albums/{gallery.a.pk}/photos/").data

        assert gallery.p2.pk not in _ids(filtered)
        assert counts[gallery.ana.pk] == 2
        assert {p["id"]: _ids(p["members"]) for p in restored}[gallery.p2.pk] == [gallery.ana.pk]


@pytest.mark.django_db
class TestTaggedMembers:
    def test_members_with_live_photos_and_their_count(self) -> None:
        gallery = Gallery()
        gallery.tag(gallery.p1, gallery.bruno, gallery.ana)
        gallery.tag(gallery.p2, gallery.ana)

        body = gallery.member.get(TAGGED).data

        assert body == [
            {"id": gallery.ana.pk, "name": "Ana", "photo_count": 2},
            {"id": gallery.bruno.pk, "name": "Bruno", "photo_count": 1},
        ]

    def test_member_whose_only_photos_are_trashed_is_absent(self) -> None:
        gallery = Gallery()
        gallery.tag(gallery.pb, gallery.carla)
        gallery.manager.delete(f"/api/albums/{gallery.b.pk}/")

        assert gallery.member.get(TAGGED).data == []

    def test_non_member_is_403(self) -> None:
        Gallery()

        assert make_auth_client(make_user(username="outsider")).get(TAGGED).status_code == 403


@pytest.mark.django_db
class TestBulk:
    def test_regression_add_and_remove_keep_every_other_tag(self) -> None:
        gallery = Gallery()
        gallery.tag(gallery.p1, gallery.ana, gallery.bruno)
        gallery.tag(gallery.p2, gallery.bruno)
        body = {
            "photo_ids": [gallery.p1.pk, gallery.p2.pk],
            "add_member_ids": [gallery.carla.pk],
            "remove_member_ids": [gallery.bruno.pk],
        }

        response = gallery.manager.post(BULK, body, format="json")

        assert response.status_code == 200
        assert gallery.tags_of(gallery.p1) == {gallery.ana.pk, gallery.carla.pk}
        assert gallery.tags_of(gallery.p2) == {gallery.carla.pk}

    def test_answers_the_photos_in_request_order(self) -> None:
        gallery = Gallery()
        body = {"photo_ids": [gallery.p2.pk, gallery.p1.pk], "add_member_ids": [gallery.ana.pk]}

        response = gallery.manager.post(BULK, body, format="json")

        assert _ids(response.data) == [gallery.p2.pk, gallery.p1.pk]
        assert all(_ids(p["members"]) == [gallery.ana.pk] for p in response.data)

    def test_existing_add_and_missing_remove_change_nothing(self) -> None:
        gallery = Gallery()
        gallery.tag(gallery.p1, gallery.ana)
        body = {
            "photo_ids": [gallery.p1.pk],
            "add_member_ids": [gallery.ana.pk],
            "remove_member_ids": [gallery.bruno.pk],
        }

        assert gallery.manager.post(BULK, body, format="json").status_code == 200
        assert gallery.tags_of(gallery.p1) == {gallery.ana.pk}

    def test_regression_atomic_failure_lists_every_offending_id(self) -> None:
        gallery = Gallery()
        gallery.tag(gallery.p1, gallery.ana)
        gallery.manager.delete(f"/api/photos/{gallery.p2.pk}/")
        body = {
            "photo_ids": [gallery.p1.pk, gallery.p2.pk, 999_999],
            "add_member_ids": [gallery.bruno.pk, 888_888],
            "remove_member_ids": [gallery.ana.pk],
        }

        response = gallery.manager.post(BULK, body, format="json")

        assert response.status_code == 404
        assert response.data["missing_photo_ids"] == [gallery.p2.pk, 999_999]
        assert response.data["missing_member_ids"] == [888_888]
        assert gallery.tags_of(gallery.p1) == {gallery.ana.pk}

    def test_more_than_200_photos_is_400(self) -> None:
        gallery = Gallery()
        body = {"photo_ids": list(range(1, 202)), "add_member_ids": [gallery.ana.pk]}

        response = gallery.manager.post(BULK, body, format="json")

        assert response.status_code == 400
        assert (response.data["photo_count"], response.data["limit"]) == (201, 200)

    def test_member_in_both_lists_is_400(self) -> None:
        gallery = Gallery()
        body = {
            "photo_ids": [gallery.p1.pk],
            "add_member_ids": [gallery.ana.pk],
            "remove_member_ids": [gallery.ana.pk],
        }

        response = gallery.manager.post(BULK, body, format="json")

        assert response.status_code == 400
        assert response.data["member_ids"] == [gallery.ana.pk]

    @pytest.mark.parametrize(
        "body",
        [
            {"photo_ids": [], "add_member_ids": [1]},
            {"photo_ids": [1]},
            {"photo_ids": [1], "add_member_ids": [], "remove_member_ids": []},
            {"add_member_ids": [1]},
            {"photo_ids": ["a"], "add_member_ids": [1]},
        ],
    )
    def test_empty_or_malformed_is_400(self, body: dict[str, object]) -> None:
        assert Gallery().manager.post(BULK, body, format="json").status_code == 400


@pytest.mark.django_db
def test_regression_no_member_field_beyond_id_and_name() -> None:
    """Readers see who is in a photo without any other data of the roll (spec 015 FR-035)."""
    gallery = Gallery()
    gallery.tag(gallery.p1, gallery.ana)

    photos = gallery.member.get("/api/photos/").data
    tagged = gallery.member.get(TAGGED).data

    assert {key for photo in photos for m in photo["members"] for key in m} == {"id", "name"}
    assert {key for m in tagged for key in m} == {"id", "name", "photo_count"}
