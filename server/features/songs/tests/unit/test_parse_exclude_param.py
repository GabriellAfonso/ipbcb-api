from features.songs.views.songs import MAX_EXCLUDE_PAIRS, _parse_exclude_param


class TestParseExcludeParam:
    def test_empty_string(self) -> None:
        assert _parse_exclude_param("") == {}

    def test_repeated_position_collects_every_song(self) -> None:
        assert _parse_exclude_param("3:12,3:34,1:7") == {3: {12, 34}, 1: {7}}

    def test_whitespace_trimmed(self) -> None:
        assert _parse_exclude_param(" 3 : 12 , 3 : 34 ") == {3: {12, 34}}

    def test_invalid_entries_ignored(self) -> None:
        assert _parse_exclude_param("abc,3:x,y:4,3:,:5,3:12") == {3: {12}}

    def test_positions_outside_1_to_4_ignored(self) -> None:
        assert _parse_exclude_param("0:1,5:2,-1:3,4:4") == {4: {4}}

    def test_keeps_only_the_first_distinct_pairs_up_to_the_limit(self) -> None:
        pairs = ",".join(f"3:{song_id}" for song_id in range(MAX_EXCLUDE_PAIRS + 50))
        assert _parse_exclude_param(pairs) == {3: set(range(MAX_EXCLUDE_PAIRS))}

    def test_repeated_pairs_do_not_use_up_the_limit(self) -> None:
        repeats = ",".join(["3:1"] * MAX_EXCLUDE_PAIRS)
        assert _parse_exclude_param(f"{repeats},3:2") == {3: {1, 2}}
