"""Malformed payloads must be refused as 400, not crash into a 500."""

import pytest

from core.domain.exceptions import ValidationError
from core.http.parsing import (
    optional_single_value,
    require_int,
    require_int_list,
    require_object_body,
)


class TestRequireObjectBody:
    def test_returns_the_dict_untouched(self) -> None:
        body = {"username": "ana"}

        assert require_object_body(body) is body

    def test_accepts_an_empty_object(self) -> None:
        assert require_object_body({}) == {}

    @pytest.mark.parametrize("body", [["a"], "abc", 42, None, 3.5, True])
    def test_rejects_anything_that_is_not_a_mapping(self, body: object) -> None:
        """Regression: `**` on a non-mapping raises TypeError outside the handler."""
        with pytest.raises(ValidationError, match="must be a JSON object"):
            require_object_body(body)

    def test_message_names_the_type_received(self) -> None:
        with pytest.raises(ValidationError, match="got list"):
            require_object_body(["a"])


class TestRequireInt:
    @pytest.mark.parametrize(("value", "expected"), [(12, 12), ("12", 12), (12.0, 12)])
    def test_coerces_what_can_be_coerced(self, value: object, expected: int) -> None:
        assert require_int(value, "song_id") == expected

    @pytest.mark.parametrize("value", ["abc", [1], {}, None, ""])
    def test_rejects_what_cannot(self, value: object) -> None:
        with pytest.raises(ValidationError, match="must be an integer"):
            require_int(value, "song_id")

    def test_message_names_the_field_and_the_value(self) -> None:
        with pytest.raises(ValidationError, match="'song_id'.*'abc'"):
            require_int("abc", "song_id")


class TestRequireIntList:
    def test_coerces_every_value_keeping_order_and_repeats(self) -> None:
        assert require_int_list(["12", 40, "12"], "member_id") == [12, 40, 12]

    def test_empty_list_is_empty(self) -> None:
        assert require_int_list([], "member_id") == []

    @pytest.mark.parametrize("bad", ["abc", "1.5", "", None])
    def test_rejects_a_value_that_is_not_an_integer(self, bad: object) -> None:
        with pytest.raises(ValidationError) as caught:
            require_int_list(["12", bad], "member_id")

        assert "member_id" in str(caught.value)
        assert repr(bad) in str(caught.value)


class TestOptionalSingleValue:
    def test_absent_is_none(self) -> None:
        assert optional_single_value([], "client_upload_id") is None

    def test_one_value_is_returned_as_text(self) -> None:
        assert optional_single_value(["abc"], "client_upload_id") == "abc"

    def test_repeated_field_names_it_and_the_count(self) -> None:
        with pytest.raises(ValidationError) as caught:
            optional_single_value(["a", "b"], "client_upload_id")

        assert "'client_upload_id'" in str(caught.value)
        assert "got 2 values" in str(caught.value)
