from features.gallery.domain.album_tree import (
    AlbumNode,
    find_cycle,
    resolve_cover_sources,
    tree_order,
)


def _node(id_: int, parent: int | None, position: int = 0, cover: bool = False) -> AlbumNode:
    return AlbumNode(id=id_, parent_id=parent, position=position, has_own_cover=cover)


# A(1) -> B(2) -> C(3); D(4) is another root.
PARENT_OF: dict[int, int | None] = {1: None, 2: 1, 3: 2, 4: None}


class TestFindCycle:
    def test_regression_moving_under_itself_is_a_cycle(self) -> None:
        assert find_cycle(1, 1, PARENT_OF) == [1]

    def test_regression_moving_under_a_grandchild_is_a_cycle(self) -> None:
        assert find_cycle(1, 3, PARENT_OF) == [3, 2, 1]

    def test_moving_under_a_child_is_a_cycle(self) -> None:
        assert find_cycle(1, 2, PARENT_OF) == [2, 1]

    def test_moving_to_root_is_never_a_cycle(self) -> None:
        assert find_cycle(3, None, PARENT_OF) is None

    def test_moving_under_an_unrelated_album_is_allowed(self) -> None:
        assert find_cycle(2, 4, PARENT_OF) is None

    def test_moving_a_child_under_its_ancestor_is_allowed(self) -> None:
        assert find_cycle(3, 1, PARENT_OF) is None

    def test_terminates_on_a_cycle_already_stored(self) -> None:
        assert find_cycle(9, 5, {5: 6, 6: 5}) is None


class TestTreeOrder:
    def test_pre_order_with_siblings_by_position_then_id(self) -> None:
        nodes = [
            _node(1, None, position=1),
            _node(2, None, position=0),
            _node(3, 1, position=0),
            _node(5, 2, position=1),
            _node(4, 2, position=1),
        ]

        assert tree_order(nodes) == [2, 4, 5, 1, 3]

    def test_empty(self) -> None:
        assert tree_order([]) == []

    def test_cycle_terminates_and_keeps_every_album(self) -> None:
        nodes = [_node(1, None), _node(2, 3), _node(3, 2)]

        assert tree_order(nodes) == [1, 2, 3]


class TestResolveCoverSources:
    def test_own_cover_is_its_own_source(self) -> None:
        assert resolve_cover_sources([_node(1, None, cover=True)]) == {1: 1}

    def test_no_cover_anywhere_below_is_none(self) -> None:
        assert resolve_cover_sources([_node(1, None), _node(2, 1)]) == {1: None, 2: None}

    def test_depth_first_not_breadth_first(self) -> None:
        # Retiros(1) -> 2024(2, no cover) -> Sábado(3, cover); Retiros -> 2025(4, cover)
        nodes = [
            _node(1, None),
            _node(2, 1, position=0),
            _node(3, 2, cover=True),
            _node(4, 1, position=1, cover=True),
        ]

        sources = resolve_cover_sources(nodes)

        assert sources[1] == 3
        assert sources[2] == 3
        assert sources[4] == 4

    def test_skips_children_without_a_cover_in_their_subtree(self) -> None:
        nodes = [_node(1, None), _node(2, 1, position=0), _node(3, 1, position=1, cover=True)]

        assert resolve_cover_sources(nodes)[1] == 3

    def test_own_cover_wins_over_descendants(self) -> None:
        nodes = [_node(1, None, cover=True), _node(2, 1, cover=True)]

        assert resolve_cover_sources(nodes)[1] == 1

    def test_cycle_terminates(self) -> None:
        nodes = [_node(1, 2), _node(2, 1)]

        assert resolve_cover_sources(nodes) == {1: None, 2: None}
