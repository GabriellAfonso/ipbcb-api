import pytest
from pydantic import ValidationError

from features.songs.dtos import SongChangesInput


def _error_locs(payload: dict[str, object]) -> list[tuple[int | str, ...]]:
    with pytest.raises(ValidationError) as caught:
        SongChangesInput.model_validate(payload)
    return [err["loc"] for err in caught.value.errors()]


class TestAcceptedChanges:
    @pytest.mark.parametrize("field", ["title", "artist"])
    def test_single_text_field_is_trimmed(self, field: str) -> None:
        changes = SongChangesInput.model_validate({field: "  Oceans  "})
        assert changes.model_dump(exclude_unset=True) == {field: "Oceans"}

    def test_link_alone(self) -> None:
        changes = SongChangesInput.model_validate({"youtube_link": " https://youtu.be/x "})
        assert changes.model_dump(exclude_unset=True) == {"youtube_link": "https://youtu.be/x"}

    def test_empty_link_is_a_change_that_clears(self) -> None:
        changes = SongChangesInput.model_validate({"youtube_link": ""})
        assert changes.model_fields_set == {"youtube_link"}
        assert changes.youtube_link == ""

    def test_dump_holds_only_the_keys_sent(self) -> None:
        changes = SongChangesInput.model_validate({"title": "A", "artist": "B"})
        assert changes.model_dump(exclude_unset=True) == {"title": "A", "artist": "B"}


class TestRejectedChanges:
    def test_empty_body(self) -> None:
        assert _error_locs({}) == [()]

    @pytest.mark.parametrize("field", ["title", "artist", "youtube_link"])
    def test_null_is_refused_on_the_field(self, field: str) -> None:
        assert _error_locs({field: None}) == [(field,)]

    @pytest.mark.parametrize("key", ["category", "id"])
    def test_unknown_key(self, key: str) -> None:
        assert _error_locs({"title": "A", key: "x"}) == [(key,)]

    @pytest.mark.parametrize("field", ["title", "artist"])
    def test_text_over_100_after_trim(self, field: str) -> None:
        assert _error_locs({field: " " + "a" * 101 + " "}) == [(field,)]

    def test_whitespace_only_title(self) -> None:
        assert _error_locs({"title": "   "}) == [("title",)]

    def test_link_not_http(self) -> None:
        assert _error_locs({"youtube_link": "ftp://x.com/a"}) == [("youtube_link",)]

    def test_link_over_200(self) -> None:
        link = "https://youtu.be/" + "a" * 184
        assert _error_locs({"youtube_link": link}) == [("youtube_link",)]
