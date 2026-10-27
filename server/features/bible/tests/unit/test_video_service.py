"""BibleVideoService with named fakes (specs/025-bible-videos US1–US3)."""

from uuid import uuid4

import pytest

from core.domain.exceptions import (
    BiblePlaceInvalidError,
    BiblePlaceNotFoundError,
    BibleVideoExistsError,
    BibleVideoInvalidUrlError,
    BibleVideoLookupFailedError,
    BibleVideoNotFoundError,
    BibleVideoOrderMismatchError,
    BibleVideoUnavailableError,
)
from features.bible.domain.canon import BiblePlace
from features.bible.services.video_service import BibleVideoService
from features.bible.tests.fakes import (
    SMALL_CANON,
    FakeBibleVideoRepository,
    FakeYouTubeMetadataClient,
)
from features.bible.video_dtos import BiblePlaceDTO, BibleVideoCreateDTO, BibleVideoOrderDTO

VIDEO_ID = "dQw4w9WgXcQ"
CREATOR = uuid4()


@pytest.fixture
def repository() -> FakeBibleVideoRepository:
    return FakeBibleVideoRepository()


@pytest.fixture
def youtube() -> FakeYouTubeMetadataClient:
    return FakeYouTubeMetadataClient()


@pytest.fixture
def service(
    repository: FakeBibleVideoRepository, youtube: FakeYouTubeMetadataClient
) -> BibleVideoService:
    return BibleVideoService(repository, youtube, SMALL_CANON)


def _places(*pairs: tuple[str, int | None]) -> list[BiblePlaceDTO]:
    return [BiblePlaceDTO(book=book, chapter=chapter) for book, chapter in pairs]


def _create(service: BibleVideoService, *pairs: tuple[str, int | None]) -> int:
    dto = BibleVideoCreateDTO(url=f"https://youtu.be/{VIDEO_ID}", places=_places(*pairs))
    return service.create(dto, CREATOR).id


class TestCreate:
    def test_reads_metadata_and_appends_to_each_place(
        self, service: BibleVideoService, repository: FakeBibleVideoRepository
    ) -> None:
        repository.add("aaaaaaaaaaa", [BiblePlace("Gn", 1)])

        video = service.create(
            BibleVideoCreateDTO(
                url=f"https://youtu.be/{VIDEO_ID}?t=90", places=_places(("gn", 1), ("Êx", None))
            ),
            CREATOR,
        )

        assert video.title == "Estudo em Gênesis"
        assert video.url == f"https://www.youtube.com/watch?v={VIDEO_ID}&t=90"
        assert [(p.book, p.chapter, p.position) for p in video.places] == [
            ("Gn", 1, 1),
            ("Êx", None, 0),
        ]

    def test_invalid_link_is_refused_before_anything(
        self, service: BibleVideoService, youtube: FakeYouTubeMetadataClient
    ) -> None:
        with pytest.raises(BibleVideoInvalidUrlError, match="vimeo"):
            service.create(
                BibleVideoCreateDTO(url="https://vimeo.com/1", places=_places(("Gn", 1))), CREATOR
            )
        assert youtube.fetched == []

    def test_no_place_is_refused(self, service: BibleVideoService) -> None:
        with pytest.raises(BiblePlaceInvalidError, match="ao menos um"):
            _create(service)

    @pytest.mark.parametrize(
        ("book", "chapter", "message"),
        [("Xy", 1, "Livro desconhecido"), ("Gn", 51, "capítulo 51")],
    )
    def test_invalid_place_is_refused(
        self, service: BibleVideoService, book: str, chapter: int, message: str
    ) -> None:
        with pytest.raises(BiblePlaceInvalidError, match=message):
            _create(service, (book, chapter))

    def test_repeated_place_spelled_differently_is_refused(
        self, service: BibleVideoService
    ) -> None:
        with pytest.raises(BiblePlaceInvalidError, match="repetido"):
            _create(service, ("Gn", 1), ("gn", 1))

    def test_duplicate_is_refused_with_the_saved_video_and_no_lookup(
        self, service: BibleVideoService, youtube: FakeYouTubeMetadataClient
    ) -> None:
        first = _create(service, ("Gn", 1))
        youtube.fetched.clear()

        with pytest.raises(BibleVideoExistsError) as caught:
            service.create(
                BibleVideoCreateDTO(
                    url=f"https://www.youtube.com/watch?v={VIDEO_ID}", places=_places(("Êx", 1))
                ),
                CREATOR,
            )

        assert caught.value.extra_context()["video"]["id"] == first  # type: ignore[index]
        assert youtube.fetched == []

    def test_losing_the_insert_race_reports_the_duplicate(
        self, service: BibleVideoService, repository: FakeBibleVideoRepository
    ) -> None:
        repository.lose_create_race = True
        with pytest.raises(BibleVideoExistsError):
            _create(service, ("Gn", 1))

    def test_youtube_refusal_and_failure_store_nothing(
        self,
        service: BibleVideoService,
        repository: FakeBibleVideoRepository,
        youtube: FakeYouTubeMetadataClient,
    ) -> None:
        youtube.unavailable = True
        with pytest.raises(BibleVideoUnavailableError):
            _create(service, ("Gn", 1))
        youtube.unavailable, youtube.failing = False, True
        with pytest.raises(BibleVideoLookupFailedError):
            _create(service, ("Gn", 1))
        assert repository.videos == {}


class TestListVideos:
    def test_places_come_in_canonical_order(
        self, service: BibleVideoService, repository: FakeBibleVideoRepository
    ) -> None:
        repository.add(VIDEO_ID, [BiblePlace("Êx", 2), BiblePlace("Gn", 3), BiblePlace("Gn", None)])
        [video] = service.list_videos()
        assert [(p.book, p.chapter) for p in video.places] == [("Gn", None), ("Gn", 3), ("Êx", 2)]


class TestReplacePlaces:
    def test_keeps_appends_and_removes(
        self, service: BibleVideoService, repository: FakeBibleVideoRepository
    ) -> None:
        repository.add("aaaaaaaaaaa", [BiblePlace("Êx", 1)])
        video = repository.add(VIDEO_ID, [BiblePlace("Gn", 1), BiblePlace("Gn", 2)])
        repository.set_order(BiblePlace("Gn", 2), [video.id])
        repository.positions[(video.id, BiblePlace("Gn", 2))] = 7

        updated = service.replace_places(video.id, _places(("Gn", 2), ("êx", 1)))

        assert updated is not None
        assert [(p.book, p.chapter, p.position) for p in updated.places] == [
            ("Gn", 2, 7),
            ("Êx", 1, 1),
        ]

    def test_empty_list_deletes_the_video(
        self, service: BibleVideoService, repository: FakeBibleVideoRepository
    ) -> None:
        video = repository.add(VIDEO_ID, [BiblePlace("Gn", 1)])
        assert service.replace_places(video.id, []) is None
        assert repository.videos == {}

    def test_unknown_video(self, service: BibleVideoService) -> None:
        with pytest.raises(BibleVideoNotFoundError):
            service.replace_places(99, _places(("Gn", 1)))


class TestRemovePlace:
    def test_removes_one_place(
        self, service: BibleVideoService, repository: FakeBibleVideoRepository
    ) -> None:
        video = repository.add(VIDEO_ID, [BiblePlace("Gn", 1), BiblePlace("Gn", None)])
        updated = service.remove_place(video.id, "gn", 1)
        assert updated is not None
        assert [(p.book, p.chapter) for p in updated.places] == [("Gn", None)]

    def test_last_place_deletes_the_video(
        self, service: BibleVideoService, repository: FakeBibleVideoRepository
    ) -> None:
        video = repository.add(VIDEO_ID, [BiblePlace("Gn", None)])
        assert service.remove_place(video.id, "Gn", None) is None
        assert repository.videos == {}

    def test_place_not_linked(
        self, service: BibleVideoService, repository: FakeBibleVideoRepository
    ) -> None:
        video = repository.add(VIDEO_ID, [BiblePlace("Gn", 1)])
        with pytest.raises(BiblePlaceNotFoundError, match="Gn 2"):
            service.remove_place(video.id, "Gn", 2)


class TestDelete:
    def test_deletes(
        self, service: BibleVideoService, repository: FakeBibleVideoRepository
    ) -> None:
        video = repository.add(VIDEO_ID, [BiblePlace("Gn", 1)])
        service.delete(video.id)
        assert repository.videos == {}

    def test_unknown_video(self, service: BibleVideoService) -> None:
        with pytest.raises(BibleVideoNotFoundError, match="id=5"):
            service.delete(5)


class TestSetOrder:
    def test_sets_positions_of_that_place_only(
        self, service: BibleVideoService, repository: FakeBibleVideoRepository
    ) -> None:
        a = repository.add("aaaaaaaaaaa", [BiblePlace("Gn", 1), BiblePlace("Gn", 2)])
        b = repository.add("bbbbbbbbbbb", [BiblePlace("Gn", 1), BiblePlace("Gn", 2)])

        service.set_order(BibleVideoOrderDTO(book="gn", chapter=1, video_ids=[b.id, a.id]))

        assert repository.video_ids_at(BiblePlace("Gn", 1)) == [b.id, a.id]
        assert repository.video_ids_at(BiblePlace("Gn", 2)) == [a.id, b.id]

    @pytest.mark.parametrize("sent", [[1], [1, 2, 3], [1, 1]])
    def test_list_must_be_exactly_the_place_videos(
        self, service: BibleVideoService, repository: FakeBibleVideoRepository, sent: list[int]
    ) -> None:
        repository.add("aaaaaaaaaaa", [BiblePlace("Gn", 1)])
        repository.add("bbbbbbbbbbb", [BiblePlace("Gn", 1)])
        with pytest.raises(BibleVideoOrderMismatchError) as caught:
            service.set_order(BibleVideoOrderDTO(book="Gn", chapter=1, video_ids=sent))
        assert caught.value.extra_context() == {"expected_video_ids": [1, 2]}
