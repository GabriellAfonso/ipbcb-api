from datetime import date, timedelta

from django.utils.timezone import now

from features.songs.models.song import Played
from features.songs.services.song_service import SongService, SuggestedPlay
from features.songs.tests.fakes import FakeSongRepository, RecordingSongPicker


def _days_ago(days: int) -> date:
    return (now() - timedelta(days=days)).date()


OLD = _days_ago(120)
OLDER = _days_ago(400)
RECENT = _days_ago(30)


class PlayLog:
    """Builds unsaved ``Played`` rows with unique ids for the fake repository."""

    def __init__(self) -> None:
        self.plays: list[Played] = []

    def add(self, song_id: int, position: int, day: date = OLD, tone: str = "G") -> Played:
        played = Played(
            id=len(self.plays) + 1, song_id=song_id, position=position, date=day, tone=tone
        )
        self.plays.append(played)
        return played


def _service(log: PlayLog, picker: RecordingSongPicker) -> tuple[SongService, FakeSongRepository]:
    repo = FakeSongRepository(plays=log.plays)
    return SongService(repo, pick_song=picker), repo


def _song_by_position(result: list[SuggestedPlay]) -> dict[int, int | None]:
    return {s.position: s.played.song_id for s in result}


def test_each_song_is_offered_once_however_often_it_was_played() -> None:
    log = PlayLog()
    for _ in range(12):
        log.add(song_id=1, position=3)
    log.add(song_id=2, position=3)
    picker = RecordingSongPicker()
    service, _ = _service(log, picker)

    service.suggest_songs()

    assert picker.offers == [[1, 2]]


def test_drawn_song_comes_with_its_latest_play_in_that_position() -> None:
    log = PlayLog()
    log.add(song_id=1, position=3, day=OLDER, tone="C")
    latest = log.add(song_id=1, position=3, day=OLD, tone="D")
    log.add(song_id=1, position=1, day=_days_ago(100), tone="E")
    service, _ = _service(log, RecordingSongPicker(choose=1))

    # Position 1 pinned to a missing play: it is skipped, so song 1 stays free for position 3.
    result = service.suggest_songs({1: 999})

    assert [(s.position, s.played) for s in result] == [(3, latest)]


def test_exclude_removes_the_song_only_from_its_position() -> None:
    log = PlayLog()
    log.add(song_id=10, position=1)
    log.add(song_id=11, position=1)
    log.add(song_id=10, position=3)
    picker = RecordingSongPicker()
    service, _ = _service(log, picker)

    result = service.suggest_songs(excluded_by_position={1: {10}})

    assert picker.offers == [[11], [10]]
    assert _song_by_position(result) == {1: 11, 3: 10}


def test_exhausted_exclusion_draws_again_without_it() -> None:
    log = PlayLog()
    log.add(song_id=1, position=3)
    log.add(song_id=2, position=3)
    picker = RecordingSongPicker()
    service, repo = _service(log, picker)

    result = service.suggest_songs(excluded_by_position={3: {1, 2}})

    assert picker.offers == [[1, 2]]
    assert repo.calls.count("get_candidate_song_ids") == 5  # 4 positions + 1 retry
    assert _song_by_position(result) == {3: 1}


def test_fallback_still_blocks_recent_and_already_used_songs() -> None:
    log = PlayLog()
    fixed = log.add(song_id=1, position=1)
    for song_id in (1, 2, 3):
        log.add(song_id=song_id, position=3)
    log.add(song_id=2, position=4, day=RECENT)
    picker = RecordingSongPicker()
    service, _ = _service(log, picker)

    result = service.suggest_songs({1: fixed.id}, excluded_by_position={3: {3}})

    assert picker.offers == [[3]]
    assert _song_by_position(result) == {1: 1, 3: 3}


def test_position_without_candidates_is_left_out() -> None:
    log = PlayLog()
    log.add(song_id=1, position=2, day=RECENT)
    service, _ = _service(log, RecordingSongPicker())

    assert service.suggest_songs(excluded_by_position={2: {5}}) == []


def test_exclude_is_ignored_on_a_fixed_position() -> None:
    log = PlayLog()
    fixed = log.add(song_id=1, position=3)
    service, _ = _service(log, RecordingSongPicker())

    result = service.suggest_songs({3: fixed.id}, excluded_by_position={3: {1}})

    assert [(s.position, s.played) for s in result] == [(3, fixed)]


def test_no_song_repeats_within_a_sunday_without_exclude() -> None:
    log = PlayLog()
    for song_id in range(1, 6):
        for position in range(1, 5):
            log.add(song_id=song_id, position=position)
    service = SongService(FakeSongRepository(plays=log.plays))

    for _ in range(50):
        song_ids = [s.played.song_id for s in service.suggest_songs()]
        assert len(song_ids) == 4
        assert len(set(song_ids)) == 4
