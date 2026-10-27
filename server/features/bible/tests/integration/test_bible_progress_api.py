"""Reading progress over HTTP (specs/025-bible-videos US4)."""

from typing import Any

import pytest
from rest_framework.test import APIClient

from conftest import make_auth_client, make_user
from features.bible.models import BibleChapterProgress
from features.bible.tests.integration.conftest import PROGRESS_URL, SYNC_URL, seed_video

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("clock")]


def _chapter(book: str, chapter: int, done: bool, at: str) -> dict[str, Any]:
    return {"type": "chapter", "book": book, "chapter": chapter, "done": done, "changed_at": at}


def _sync(client: APIClient, *changes: dict[str, Any]) -> Any:
    return client.post(SYNC_URL, {"changes": list(changes)}, format="json")


def test_sync_then_read_the_state() -> None:
    client = make_auth_client(make_user())
    video = seed_video("aaaaaaaaaaa", ("Gn", 1, 0))

    response = _sync(
        client,
        _chapter("gn", 1, True, "2026-10-27T09:00:00-03:00"),
        _chapter("Sl", 23, True, "2026-10-27T09:00:00-03:00"),
        {"type": "video", "video_id": video.pk, "done": True, "changed_at": "2026-10-27T12:00:00Z"},
        {"type": "video", "video_id": 999, "done": True, "changed_at": "2026-10-27T12:00:00Z"},
        _chapter("Gn", 51, True, "2026-10-27T12:00:00Z"),
    )

    assert response.status_code == 200
    assert response.data == {
        "accepted": [0, 1, 2],
        "rejected": [
            {"index": 3, "reason": "unknown_video"},
            {"index": 4, "reason": "unknown_chapter"},
        ],
    }
    state = client.get(PROGRESS_URL)
    assert state.data == {"chapters": {"Gn": [1], "Sl": [23]}, "videos": [video.pk]}
    assert state["Cache-Control"] == "private, no-store"


def test_an_older_offline_mark_does_not_bring_back_an_unmark() -> None:
    client = make_auth_client(make_user())
    _sync(client, _chapter("Gn", 1, False, "2026-10-27T10:05:00-03:00"))
    _sync(client, _chapter("Gn", 1, True, "2026-10-27T10:00:00-03:00"))

    assert client.get(PROGRESS_URL).data["chapters"] == {}
    assert BibleChapterProgress.objects.get().done is False


def test_time_without_offset_and_far_future_are_rejected_per_item() -> None:
    client = make_auth_client(make_user())
    response = _sync(
        client,
        _chapter("Gn", 1, True, "2026-10-27T10:00:00"),
        _chapter("Gn", 2, True, "2026-10-27T13:06:00Z"),
        _chapter("Gn", 3, True, "2026-10-27T13:04:00Z"),
    )
    assert response.data["accepted"] == [2]
    assert [r["reason"] for r in response.data["rejected"]] == [
        "changed_at_without_offset",
        "changed_at_in_future",
    ]


@pytest.mark.parametrize(
    "body",
    [
        {"changes": []},
        {"changes": [_chapter("Gn", 1, True, "2026-10-27T10:00:00Z")] * 501},
        {"changes": [{**_chapter("Gn", 1, True, "2026-10-27T10:00:00Z"), "note": "x"}]},
        {
            "changes": [
                {"type": "book", "book": "Gn", "done": True, "changed_at": "2026-10-27T10:00:00Z"}
            ]
        },
        {"items": []},
        [],
    ],
)
def test_shape_errors_refuse_the_whole_batch(body: Any) -> None:
    response = make_auth_client(make_user()).post(SYNC_URL, body, format="json")
    assert (response.status_code, response.data["error_code"]) == (400, "VALIDATION_ERROR")
    assert not BibleChapterProgress.objects.exists()


def test_a_whole_book_fits_in_one_batch() -> None:
    client = make_auth_client(make_user())
    changes = [_chapter("Sl", n, True, "2026-10-27T10:00:00Z") for n in range(1, 151)]
    response = _sync(client, *changes)
    assert len(response.data["accepted"]) == 150
    assert client.get(PROGRESS_URL).data["chapters"]["Sl"] == list(range(1, 151))


def test_each_user_sees_only_their_marks() -> None:
    ana = make_auth_client(make_user(username="ana"))
    bia = make_auth_client(make_user(username="bia"))
    _sync(ana, _chapter("Gn", 1, True, "2026-10-27T10:00:00Z"))
    assert bia.get(PROGRESS_URL).data == {"chapters": {}, "videos": []}


def test_signed_out_is_401() -> None:
    assert APIClient().get(PROGRESS_URL).status_code == 401
    assert _sync(APIClient(), _chapter("Gn", 1, True, "2026-10-27T10:00:00Z")).status_code == 401
