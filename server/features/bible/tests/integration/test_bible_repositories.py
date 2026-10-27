"""ORM repositories of feature 025 against the test database."""

from datetime import UTC, datetime, timedelta

import pytest
from django.db import IntegrityError

from conftest import make_user
from features.bible.domain.canon import BiblePlace
from features.bible.domain.youtube_links import YouTubeKind
from features.bible.models import BibleChapterProgress, BibleVideo, BibleVideoPlace
from features.bible.progress_dtos import ChapterMarkDTO, VideoMarkDTO
from features.bible.repositories.progress_repository import BibleProgressRepositoryImpl
from features.bible.repositories.video_repository import BibleVideoRepositoryImpl
from features.bible.tests.integration.conftest import seed_video
from features.bible.video_dtos import BibleVideoNewDTO

pytestmark = pytest.mark.django_db

AT = datetime(2026, 10, 27, 13, 0, tzinfo=UTC)


def _new(youtube_id: str) -> BibleVideoNewDTO:
    return BibleVideoNewDTO(
        kind=YouTubeKind.VIDEO,
        youtube_id=youtube_id,
        url=f"https://www.youtube.com/watch?v={youtube_id}",
        title="Título",
        thumbnail_url="https://i.ytimg.com/vi/x/hqdefault.jpg",
    )


class TestBibleVideoRepository:
    repository = BibleVideoRepositoryImpl()

    def test_create_appends_after_the_last_position_of_each_place(self) -> None:
        seed_video("aaaaaaaaaaa", ("Gn", 1, 4), ("Gn", None, 0))
        user = make_user()

        video = self.repository.create(
            _new("bbbbbbbbbbb"),
            [BiblePlace("Gn", 1), BiblePlace("Gn", None), BiblePlace("Êx", 2)],
            user.pk,
        )

        assert video is not None
        positions = {(p.book, p.chapter): p.position for p in video.places}
        assert positions == {("Gn", 1): 5, ("Gn", None): 1, ("Êx", 2): 0}
        assert BibleVideo.objects.get(pk=video.id).created_by_id == user.pk

    def test_create_of_a_taken_target_returns_none_and_keeps_nothing(self) -> None:
        seed_video("aaaaaaaaaaa", ("Gn", 1, 0))
        assert (
            self.repository.create(_new("aaaaaaaaaaa"), [BiblePlace("Êx", 1)], make_user().pk)
            is None
        )
        assert BibleVideoPlace.objects.filter(book="Êx").count() == 0

    def test_whole_book_place_is_unique_per_video(self) -> None:
        video = seed_video("aaaaaaaaaaa", ("Gn", None, 0))
        with pytest.raises(IntegrityError):
            BibleVideoPlace.objects.create(video=video, book="Gn", chapter=None, position=1)

    def test_find_get_and_list(self) -> None:
        first = seed_video("aaaaaaaaaaa", ("Gn", 1, 0))
        seed_video("bbbbbbbbbbb", ("Gn", 2, 0))
        assert self.repository.find_by_target(YouTubeKind.VIDEO, "aaaaaaaaaaa").id == first.pk  # type: ignore[union-attr]
        assert self.repository.find_by_target(YouTubeKind.PLAYLIST, "aaaaaaaaaaa") is None
        assert self.repository.get(999) is None
        assert [v.youtube_id for v in self.repository.list_all()] == ["aaaaaaaaaaa", "bbbbbbbbbbb"]

    def test_change_places_removes_and_appends(self) -> None:
        video = seed_video("aaaaaaaaaaa", ("Gn", 1, 3), ("Gn", 2, 0))
        seed_video("bbbbbbbbbbb", ("Êx", 1, 0))

        self.repository.change_places(video.pk, [BiblePlace("Êx", 1)], {BiblePlace("Gn", 2)})

        rows = BibleVideoPlace.objects.filter(video=video)
        assert {(r.book, r.chapter, r.position) for r in rows} == {("Gn", 1, 3), ("Êx", 1, 1)}

    def test_order_of_one_place(self) -> None:
        a = seed_video("aaaaaaaaaaa", ("Gn", 1, 0), ("Gn", None, 0))
        b = seed_video("bbbbbbbbbbb", ("Gn", 1, 1), ("Gn", None, 1))

        self.repository.set_order(BiblePlace("Gn", 1), [b.pk, a.pk])

        assert self.repository.video_ids_at(BiblePlace("Gn", 1)) == [b.pk, a.pk]
        assert self.repository.video_ids_at(BiblePlace("Gn", None)) == [a.pk, b.pk]

    def test_ties_are_ordered_by_video_id(self) -> None:
        a = seed_video("aaaaaaaaaaa", ("Gn", 1, 0))
        b = seed_video("bbbbbbbbbbb", ("Gn", 1, 0))
        assert self.repository.video_ids_at(BiblePlace("Gn", 1)) == [a.pk, b.pk]

    def test_delete_removes_places(self) -> None:
        video = seed_video("aaaaaaaaaaa", ("Gn", 1, 0))
        self.repository.delete(video.pk)
        assert not BibleVideoPlace.objects.exists()


class TestBibleProgressRepository:
    repository = BibleProgressRepositoryImpl()

    def test_save_marks_inserts_then_overwrites(self) -> None:
        user = make_user()
        video = seed_video("aaaaaaaaaaa", ("Gn", 1, 0))
        first = ChapterMarkDTO(book="Gn", chapter=1, done=True, changed_at=AT)
        later = first.model_copy(update={"done": False, "changed_at": AT + timedelta(minutes=1)})

        self.repository.save_marks(
            user.pk, [first], [VideoMarkDTO(video_id=video.pk, done=True, changed_at=AT)]
        )
        self.repository.save_marks(user.pk, [later], [])

        assert self.repository.chapter_marks(user.pk, {"Gn"}) == [later]
        assert BibleChapterProgress.objects.count() == 1
        assert self.repository.done_chapters(user.pk) == []
        assert self.repository.done_video_ids(user.pk) == [video.pk]

    def test_reads_are_per_user_and_filtered(self) -> None:
        ana, bia = make_user(username="ana"), make_user(username="bia")
        mark = ChapterMarkDTO(book="Gn", chapter=1, done=True, changed_at=AT)
        self.repository.save_marks(ana.pk, [mark], [])
        assert self.repository.chapter_marks(bia.pk, {"Gn"}) == []
        assert self.repository.chapter_marks(ana.pk, {"Êx"}) == []
        assert self.repository.done_chapters(ana.pk) == [("Gn", 1)]

    def test_existing_video_ids(self) -> None:
        video = seed_video("aaaaaaaaaaa", ("Gn", 1, 0))
        assert self.repository.existing_video_ids({video.pk, 999}) == {video.pk}

    def test_progress_goes_with_the_user_and_the_video(self) -> None:
        user = make_user()
        video = seed_video("aaaaaaaaaaa", ("Gn", 1, 0))
        self.repository.save_marks(
            user.pk,
            [ChapterMarkDTO(book="Gn", chapter=1, done=True, changed_at=AT)],
            [VideoMarkDTO(video_id=video.pk, done=True, changed_at=AT)],
        )
        video.delete()
        assert self.repository.done_video_ids(user.pk) == []
        user.delete()
        assert not BibleChapterProgress.objects.exists()
