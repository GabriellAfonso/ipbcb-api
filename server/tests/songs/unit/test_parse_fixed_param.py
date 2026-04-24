from features.songs.views.songs import _parse_fixed_param


class TestParseFixedParam:
    def test_empty_string(self) -> None:
        assert _parse_fixed_param("") == {}

    def test_valid_single(self) -> None:
        assert _parse_fixed_param("1:12") == {1: 12}

    def test_valid_multiple(self) -> None:
        assert _parse_fixed_param("1:12,3:45") == {1: 12, 3: 45}

    def test_ignores_position_below_1(self) -> None:
        assert _parse_fixed_param("0:10") == {}

    def test_ignores_position_above_4(self) -> None:
        assert _parse_fixed_param("5:10") == {}

    def test_ignores_entry_without_colon(self) -> None:
        assert _parse_fixed_param("abc") == {}

    def test_ignores_non_numeric_values(self) -> None:
        assert _parse_fixed_param("1:abc") == {}

    def test_strips_whitespace(self) -> None:
        assert _parse_fixed_param(" 2 : 99 , 3 : 100 ") == {2: 99, 3: 100}

    def test_mixed_valid_and_invalid(self) -> None:
        result = _parse_fixed_param("1:10,bad,5:20,3:30")
        assert result == {1: 10, 3: 30}

    def test_boundary_positions(self) -> None:
        assert _parse_fixed_param("1:1,4:4") == {1: 1, 4: 4}
