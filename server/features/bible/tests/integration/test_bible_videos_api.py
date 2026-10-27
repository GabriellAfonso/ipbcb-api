"""Bible videos over HTTP (specs/025-bible-videos US1–US3), with a fake YouTube."""

from typing import Any

import pytest
from rest_framework.test import APIClient

from conftest import make_member_client, make_role_client, make_user
from core.domain.access import Role
from features.bible.models import BibleVideo, BibleVideoPlace, BibleVideoProgress
from features.bible.tests.fakes import FakeYouTubeMetadataClient
from features.bible.tests.integration.conftest import (
    ORDER_URL,
    VIDEOS_URL,
    places_url,
    seed_video,
    video_url,
)

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("youtube")]

VIDEO_ID = "dQw4w9WgXcQ"


def _leader() -> APIClient:
    client, _ = make_role_client(Role.LEADER, username="lider")
    return client


def _post(client: APIClient, url: str = f"https://youtu.be/{VIDEO_ID}", **body: Any) -> Any:
    payload = {"url": url, "places": [{"book": "gn", "chapter": 1}], **body}
    return client.post(VIDEOS_URL, payload, format="json")


def _place_rows(video_id: int) -> set[tuple[str, int | None, int]]:
    rows = BibleVideoPlace.objects.filter(video_id=video_id)
    return {(r.book, r.chapter, r.position) for r in rows}


class TestCreate:
    def test_leader_saves_a_link_to_places(self, youtube: FakeYouTubeMetadataClient) -> None:
        seed_video("aaaaaaaaaaa", ("Gn", 1, 0))

        response = _post(
            _leader(), places=[{"book": "gn", "chapter": 1}, {"book": "Êx", "chapter": None}]
        )

        assert response.status_code == 201
        assert response.data["title"] == "Estudo em Gênesis"
        assert response.data["kind"] == "video"
        assert response.data["url"] == f"https://www.youtube.com/watch?v={VIDEO_ID}"
        assert response.data["places"] == [
            {"book": "Gn", "chapter": 1, "position": 1},
            {"book": "Êx", "chapter": None, "position": 0},
        ]

    def test_admin_saves_too(self) -> None:
        client, _ = make_role_client(Role.ADMIN, username="admin")
        assert _post(client).status_code == 201

    def test_duplicate_answers_409_with_the_video(self) -> None:
        client = _leader()
        first = _post(client).data
        response = _post(client, url=f"https://www.youtube.com/watch?v={VIDEO_ID}&t=30")

        assert response.status_code == 409
        assert response.data["error_code"] == "BIBLE_VIDEO_EXISTS"
        assert response.data["video"] == first
        assert BibleVideo.objects.count() == 1

    def test_invalid_link(self) -> None:
        response = _post(_leader(), url="https://vimeo.com/123")
        assert (response.status_code, response.data["error_code"]) == (
            400,
            "BIBLE_VIDEO_INVALID_URL",
        )

    @pytest.mark.parametrize(
        "places", [[], [{"book": "Xy", "chapter": 1}], [{"book": "Gn", "chapter": 51}]]
    )
    def test_invalid_places(self, places: list[dict[str, Any]]) -> None:
        response = _post(_leader(), places=places)
        assert (response.status_code, response.data["error_code"]) == (400, "BIBLE_PLACE_INVALID")
        assert not BibleVideo.objects.exists()

    def test_unavailable_video(self, youtube: FakeYouTubeMetadataClient) -> None:
        youtube.unavailable = True
        response = _post(_leader())
        assert (response.status_code, response.data["error_code"]) == (
            400,
            "BIBLE_VIDEO_UNAVAILABLE",
        )
        assert not BibleVideo.objects.exists()

    def test_youtube_down_is_503(self, youtube: FakeYouTubeMetadataClient) -> None:
        youtube.failing = True
        response = _post(_leader())
        assert (response.status_code, response.data["error_code"]) == (
            503,
            "BIBLE_VIDEO_LOOKUP_FAILED",
        )

    def test_unknown_field_is_a_validation_error(self) -> None:
        response = _post(_leader(), title="meu título")
        assert (response.status_code, response.data["error_code"]) == (400, "VALIDATION_ERROR")

    def test_media_and_members_are_refused(self) -> None:
        media, _ = make_role_client(Role.MEDIA, username="midia")
        member, _ = make_member_client()
        assert _post(media).status_code == 403
        assert _post(member).status_code == 403
        assert _post(APIClient()).status_code == 401


class TestList:
    def test_public_list_with_places_in_canonical_order(self) -> None:
        video = seed_video(VIDEO_ID, ("Êx", 2, 0), ("Gn", 3, 1), ("Gn", None, 0))
        response = APIClient().get(VIDEOS_URL)

        assert response.status_code == 200
        assert response.data == [
            {
                "id": video.pk,
                "kind": "video",
                "youtube_id": VIDEO_ID,
                "url": f"https://www.youtube.com/watch?v={VIDEO_ID}",
                "title": f"Vídeo {VIDEO_ID}",
                "thumbnail_url": f"https://i.ytimg.com/vi/{VIDEO_ID}/hqdefault.jpg",
                "places": [
                    {"book": "Gn", "chapter": None, "position": 0},
                    {"book": "Gn", "chapter": 3, "position": 1},
                    {"book": "Êx", "chapter": 2, "position": 0},
                ],
            }
        ]
        assert "Cache-Control" not in response

    def test_etag_answers_304_until_something_changes(self) -> None:
        video = seed_video(VIDEO_ID, ("Gn", 1, 0))
        etag = APIClient().get(VIDEOS_URL)["ETag"]

        assert APIClient().get(VIDEOS_URL, HTTP_IF_NONE_MATCH=etag).status_code == 304
        _leader().delete(f"{places_url(video.pk)}?book=Gn&chapter=1")
        assert APIClient().get(VIDEOS_URL, HTTP_IF_NONE_MATCH=etag).status_code == 200

    def test_translation_routes_still_work(self) -> None:
        assert APIClient().get("/api/bible/").status_code == 200
        assert APIClient().get("/api/bible/NAA/").status_code == 200


class TestPlaces:
    def test_replace_keeps_appends_and_removes(self) -> None:
        seed_video("aaaaaaaaaaa", ("Êx", 1, 0))
        video = seed_video(VIDEO_ID, ("Gn", 1, 0), ("Gn", 2, 5))

        response = _leader().put(
            places_url(video.pk),
            {"places": [{"book": "Gn", "chapter": 2}, {"book": "êx", "chapter": 1}]},
            format="json",
        )

        assert response.status_code == 200
        assert _place_rows(video.pk) == {("Gn", 2, 5), ("Êx", 1, 1)}

    def test_replace_with_nothing_deletes_the_video(self) -> None:
        video = seed_video(VIDEO_ID, ("Gn", 1, 0))
        response = _leader().put(places_url(video.pk), {"places": []}, format="json")
        assert response.status_code == 204
        assert not BibleVideo.objects.exists()

    def test_remove_one_place_then_the_last(self) -> None:
        video = seed_video(VIDEO_ID, ("Gn", 1, 0), ("Gn", None, 0))
        client = _leader()

        first = client.delete(f"{places_url(video.pk)}?book=gn&chapter=1")
        last = client.delete(f"{places_url(video.pk)}?book=Gn")

        assert first.status_code == 200
        assert first.data["places"] == [{"book": "Gn", "chapter": None, "position": 0}]
        assert last.status_code == 204
        assert not BibleVideo.objects.exists()

    def test_remove_a_place_the_video_is_not_in(self) -> None:
        video = seed_video(VIDEO_ID, ("Gn", 1, 0))
        response = _leader().delete(f"{places_url(video.pk)}?book=Gn&chapter=2")
        assert (response.status_code, response.data["error_code"]) == (404, "BIBLE_PLACE_NOT_FOUND")

    def test_remove_without_book_is_a_validation_error(self) -> None:
        video = seed_video(VIDEO_ID, ("Gn", 1, 0))
        response = _leader().delete(places_url(video.pk))
        assert (response.status_code, response.data["error_code"]) == (400, "VALIDATION_ERROR")

    def test_unknown_video(self) -> None:
        response = _leader().put(places_url(999), {"places": []}, format="json")
        assert (response.status_code, response.data["error_code"]) == (404, "BIBLE_VIDEO_NOT_FOUND")


class TestDeleteAndOrder:
    def test_delete_removes_the_video_and_its_progress(self) -> None:
        video = seed_video(VIDEO_ID, ("Gn", 1, 0))
        user = make_user(username="ana")
        BibleVideoProgress.objects.create(
            user=user, video=video, done=True, changed_at="2026-10-27T13:00Z"
        )

        assert _leader().delete(video_url(video.pk)).status_code == 204
        assert not BibleVideo.objects.exists()
        assert not BibleVideoProgress.objects.exists()

    def test_order_one_place(self) -> None:
        a = seed_video("aaaaaaaaaaa", ("Gn", 1, 0), ("Gn", 2, 0))
        b = seed_video("bbbbbbbbbbb", ("Gn", 1, 1), ("Gn", 2, 1))

        response = _leader().put(
            ORDER_URL, {"book": "Gn", "chapter": 1, "video_ids": [b.pk, a.pk]}, format="json"
        )

        assert response.status_code == 204
        assert _place_rows(b.pk) == {("Gn", 1, 0), ("Gn", 2, 1)}
        assert _place_rows(a.pk) == {("Gn", 1, 1), ("Gn", 2, 0)}

    def test_order_mismatch(self) -> None:
        a = seed_video("aaaaaaaaaaa", ("Gn", None, 0))
        seed_video("bbbbbbbbbbb", ("Gn", None, 1))
        response = _leader().put(
            ORDER_URL, {"book": "Gn", "chapter": None, "video_ids": [a.pk, a.pk]}, format="json"
        )
        assert (response.status_code, response.data["error_code"]) == (
            400,
            "BIBLE_VIDEO_ORDER_MISMATCH",
        )
        assert len(response.data["expected_video_ids"]) == 2

    def test_media_cannot_delete_nor_order(self) -> None:
        video = seed_video(VIDEO_ID, ("Gn", 1, 0))
        media, _ = make_role_client(Role.MEDIA, username="midia")
        assert media.delete(video_url(video.pk)).status_code == 403
        body = {"book": "Gn", "chapter": 1, "video_ids": [video.pk]}
        assert media.put(ORDER_URL, body, format="json").status_code == 403
