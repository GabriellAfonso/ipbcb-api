from datetime import UTC, date, datetime, timedelta, timezone

from features.gallery.domain.trash_rules import purge_on, purge_order, subtree_ids

TREE = {1: None, 2: 1, 3: 2, 4: 1, 5: None}


class TestSubtreeIds:
    def test_leaf_is_alone(self) -> None:
        assert subtree_ids(3, TREE) == [3]

    def test_root_takes_every_descendant(self) -> None:
        assert sorted(subtree_ids(1, TREE)) == [1, 2, 3, 4]

    def test_middle_node_leaves_parent_and_siblings(self) -> None:
        assert subtree_ids(2, TREE) == [2, 3]

    def test_root_comes_first(self) -> None:
        assert subtree_ids(1, TREE)[0] == 1

    def test_cycle_terminates(self) -> None:
        assert sorted(subtree_ids(1, {1: 2, 2: 1})) == [1, 2]


class TestPurgeOrder:
    def test_chain_deepest_first(self) -> None:
        assert purge_order([1, 2, 3], {1: None, 2: 1, 3: 2}) == [3, 2, 1]

    def test_children_before_parent_with_siblings(self) -> None:
        order = purge_order([1, 2, 3, 4], TREE)
        assert order.index(3) < order.index(2) < order.index(1)
        assert order.index(4) < order.index(1)

    def test_depth_counts_only_within_the_set(self) -> None:
        # 2's parent 1 is not being purged, so 2 is a top of the set.
        assert purge_order([2, 3], TREE) == [3, 2]

    def test_cycle_terminates(self) -> None:
        assert sorted(purge_order([1, 2], {1: 2, 2: 1})) == [1, 2]


class TestPurgeOn:
    def test_thirty_days_later_crossing_a_month(self) -> None:
        assert purge_on(datetime(2026, 9, 29, 12, 0, tzinfo=UTC)) == date(2026, 10, 29)

    def test_date_is_taken_in_utc(self) -> None:
        brasilia = timezone(timedelta(hours=-3))
        deleted = datetime(2026, 9, 29, 22, 0, tzinfo=brasilia)  # 01:00 UTC on the 30th
        assert purge_on(deleted) == date(2026, 10, 30)
