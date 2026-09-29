import pytest

from core.domain.exceptions import TagBulkLimitError, TagListOverlapError, ValidationError
from features.gallery.domain.tag_rules import (
    TAG_BULK_PHOTO_LIMIT,
    TagDiff,
    bulk_diff,
    dedupe,
    normalise_bulk,
    replace_diff,
)


class TestDedupe:
    def test_keeps_first_appearance(self) -> None:
        assert dedupe([3, 1, 3, 2, 1]) == [3, 1, 2]

    def test_empty(self) -> None:
        assert dedupe([]) == []


class TestNormaliseBulk:
    def test_dedupes_every_list(self) -> None:
        request = normalise_bulk([2, 1, 2], [12, 12], [40, 40])

        assert request.photo_ids == [2, 1]
        assert request.add_member_ids == [12]
        assert request.remove_member_ids == [40]

    def test_member_lists_may_be_one_sided(self) -> None:
        assert normalise_bulk([1], [], [40]).remove_member_ids == [40]

    def test_no_photo_is_refused(self) -> None:
        with pytest.raises(ValidationError, match="photo_ids"):
            normalise_bulk([], [12], [])

    def test_no_member_in_either_list_is_refused(self) -> None:
        with pytest.raises(ValidationError, match="add_member_ids"):
            normalise_bulk([1], [], [])

    def test_member_in_both_lists_is_refused(self) -> None:
        with pytest.raises(TagListOverlapError) as caught:
            normalise_bulk([1], [12, 40], [40, 12, 7])

        assert caught.value.member_ids == [12, 40]

    def test_limit_counts_distinct_photos(self) -> None:
        ids = list(range(1, TAG_BULK_PHOTO_LIMIT + 1))

        assert len(normalise_bulk(ids + ids, [12], []).photo_ids) == TAG_BULK_PHOTO_LIMIT

    def test_one_over_the_limit_is_refused(self) -> None:
        with pytest.raises(TagBulkLimitError) as caught:
            normalise_bulk(range(1, TAG_BULK_PHOTO_LIMIT + 2), [12], [])

        assert (caught.value.photo_count, caught.value.limit) == (201, 200)

    def test_emptiness_is_checked_before_the_limit(self) -> None:
        with pytest.raises(ValidationError) as caught:
            normalise_bulk(range(1, 500), [], [])

        assert not isinstance(caught.value, TagBulkLimitError)


class TestReplaceDiff:
    def test_adds_missing_and_removes_extra(self) -> None:
        assert replace_diff(1, {12, 40}, [12, 7]) == TagDiff(added={1: [7]}, removed={1: [40]})

    def test_empty_desired_clears(self) -> None:
        assert replace_diff(1, {12, 40}, []) == TagDiff(removed={1: [12, 40]})

    def test_same_set_changes_nothing(self) -> None:
        assert replace_diff(1, {12}, [12, 12]).is_empty


class TestBulkDiff:
    def test_only_real_changes_per_photo(self) -> None:
        diff = bulk_diff({1: {12, 40}, 2: {40}, 3: set()}, add=[7], remove=[40])

        assert diff.added == {1: [7], 2: [7], 3: [7]}
        assert diff.removed == {1: [40], 2: [40]}

    def test_existing_add_and_missing_remove_are_no_ops(self) -> None:
        assert bulk_diff({1: {12}}, add=[12], remove=[40]).is_empty

    def test_changed_photo_ids_is_the_sorted_union(self) -> None:
        diff = bulk_diff({3: set(), 1: {40}}, add=[], remove=[40])

        assert diff.changed_photo_ids == [1]
