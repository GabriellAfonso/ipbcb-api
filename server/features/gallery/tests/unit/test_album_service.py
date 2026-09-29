"""AlbumService with named fakes. ``django_db`` only because the service opens transactions;
every row lives in the fakes."""

from datetime import date

import pytest

from core.domain.exceptions import (
    AlbumCycleError,
    AlbumNotFoundError,
    DuplicateAlbumNameError,
    OrderMismatchError,
    ValidationError,
)
from features.gallery.dtos.gallery_dtos import AlbumChanges, AlbumCreate, SiblingOrder
from features.gallery.services.album_service import AlbumService
from features.gallery.tests.fakes import FakeAlbumRepository, FakeGalleryFileStorage


def _service() -> tuple[AlbumService, FakeAlbumRepository]:
    albums = FakeAlbumRepository()
    return AlbumService(albums, FakeGalleryFileStorage()), albums


@pytest.mark.django_db
class TestCreate:
    def test_root_with_defaults(self) -> None:
        service, _ = _service()

        album = service.create(AlbumCreate(name="  Retiros "))

        assert (album.name, album.parent_id, album.description, album.event_date) == (
            "Retiros",
            None,
            "",
            None,
        )
        assert album.cover_path is None and album.cover_source_album_id is None

    def test_child_goes_last_among_its_siblings(self) -> None:
        service, albums = _service()
        parent = albums.add("Retiros")
        albums.add("2025", parent_id=parent)

        child = service.create(AlbumCreate(name="2026", parent_id=parent))

        assert albums.records[child.id].position == 1
        assert child.parent_id == parent

    def test_blank_name(self) -> None:
        service, _ = _service()

        with pytest.raises(ValidationError, match="vazio"):
            service.create(AlbumCreate(name="   "))

    def test_unknown_parent(self) -> None:
        service, _ = _service()

        with pytest.raises(AlbumNotFoundError):
            service.create(AlbumCreate(name="2026", parent_id=99))

    def test_regression_duplicate_root_name(self) -> None:
        service, albums = _service()
        albums.add("Retiros")

        with pytest.raises(DuplicateAlbumNameError):
            service.create(AlbumCreate(name="Retiros"))

    def test_duplicate_child_name(self) -> None:
        service, albums = _service()
        parent = albums.add("Retiros")
        albums.add("2025", parent_id=parent)

        with pytest.raises(DuplicateAlbumNameError):
            service.create(AlbumCreate(name="2025", parent_id=parent))

    def test_same_name_under_another_parent(self) -> None:
        service, albums = _service()
        albums.add("2025", parent_id=albums.add("Retiros"))

        album = service.create(AlbumCreate(name="2025", parent_id=albums.add("Acampamentos")))

        assert album.name == "2025"


@pytest.mark.django_db
class TestUpdate:
    def test_rename(self) -> None:
        service, albums = _service()
        album_id = albums.add("Retiro")

        assert service.update(album_id, AlbumChanges(name="Retiros")).name == "Retiros"

    def test_rename_to_a_sibling_name(self) -> None:
        service, albums = _service()
        albums.add("Cultos")
        album_id = albums.add("Retiros")

        with pytest.raises(DuplicateAlbumNameError):
            service.update(album_id, AlbumChanges(name="Cultos"))

    def test_move_to_root_goes_last(self) -> None:
        service, albums = _service()
        albums.add("Cultos")
        child = albums.add("2026", parent_id=albums.add("Retiros"))

        album = service.update(child, AlbumChanges(parent_id=None))

        assert album.parent_id is None
        assert albums.records[child].position == 2
        assert albums.locked_parent_map

    def test_absent_parent_does_not_move(self) -> None:
        service, albums = _service()
        parent = albums.add("Retiros")
        child = albums.add("2026", parent_id=parent)

        album = service.update(child, AlbumChanges(description="Acampamento"))

        assert (album.parent_id, album.description) == (parent, "Acampamento")

    def test_same_parent_keeps_the_position(self) -> None:
        service, albums = _service()
        parent = albums.add("Retiros")
        albums.add("2025", parent_id=parent)
        child = albums.add("2026", parent_id=parent)

        service.update(child, AlbumChanges(parent_id=parent, name="2026"))

        assert albums.records[child].position == 1

    def test_regression_move_under_itself(self) -> None:
        service, albums = _service()
        album_id = albums.add("Retiros")

        with pytest.raises(AlbumCycleError) as caught:
            service.update(album_id, AlbumChanges(parent_id=album_id))

        assert caught.value.chain == [album_id]
        assert albums.records[album_id].parent_id is None

    def test_regression_move_under_a_descendant(self) -> None:
        service, albums = _service()
        root = albums.add("A")
        grandchild = albums.add("C", parent_id=albums.add("B", parent_id=root))

        with pytest.raises(AlbumCycleError) as caught:
            service.update(root, AlbumChanges(parent_id=grandchild))

        assert str(root) in str(caught.value) and str(grandchild) in str(caught.value)
        assert albums.records[root].parent_id is None

    def test_event_date_null_clears_it(self) -> None:
        service, albums = _service()
        album_id = albums.add("Retiros")
        albums.update(album_id, {"event_date": date(2026, 3, 14)})

        assert service.update(album_id, AlbumChanges(event_date=None)).event_date is None

    def test_unknown_album(self) -> None:
        service, _ = _service()

        with pytest.raises(AlbumNotFoundError):
            service.update(99, AlbumChanges(name="x"))

    def test_unknown_parent(self) -> None:
        service, albums = _service()

        with pytest.raises(AlbumNotFoundError):
            service.update(albums.add("Retiros"), AlbumChanges(parent_id=99))


@pytest.mark.django_db
class TestValidatePlacement:
    def test_passes_for_a_valid_new_album(self) -> None:
        service, albums = _service()

        service.validate_placement(None, "2026", albums.add("Retiros"))

    def test_refuses_a_cycle(self) -> None:
        service, albums = _service()
        root = albums.add("A")
        child = albums.add("B", parent_id=root)

        with pytest.raises(AlbumCycleError):
            service.validate_placement(root, "A", child)

    def test_refuses_a_duplicate_but_not_the_album_itself(self) -> None:
        service, albums = _service()
        album_id = albums.add("Retiros")
        albums.add("Cultos")

        service.validate_placement(album_id, "Retiros", None)
        with pytest.raises(DuplicateAlbumNameError):
            service.validate_placement(album_id, "Cultos", None)


class TestListAlbums:
    def test_tree_order_with_empty_albums(self) -> None:
        service, albums = _service()
        retreats = albums.add("Retiros")
        worship = albums.add("Cultos")
        child = albums.add("2026", parent_id=retreats)

        assert [album.id for album in service.list_albums()] == [retreats, child, worship]

    def test_cover_comes_depth_first_from_a_sub_album(self) -> None:
        service, albums = _service()
        root = albums.add("Retiros")
        year = albums.add("2024", parent_id=root)
        saturday = albums.add("Sábado", parent_id=year, cover_name="gallery/covers/3/s.jpg")
        albums.add("2025", parent_id=root, cover_name="gallery/covers/4/y.jpg")

        by_id = {album.id: album for album in service.list_albums()}

        assert by_id[root].cover_source_album_id == saturday
        assert by_id[root].cover_path == "/ipbcb/media/gallery/covers/3/s.jpg"

    def test_own_cover_and_no_cover(self) -> None:
        service, albums = _service()
        covered = albums.add("Com capa", cover_name="gallery/covers/1/c.jpg")
        bare = albums.add("Sem capa")

        by_id = {album.id: album for album in service.list_albums()}

        assert by_id[covered].cover_source_album_id == covered
        assert (by_id[bare].cover_path, by_id[bare].cover_source_album_id) == (None, None)

    def test_view_of_unknown_album(self) -> None:
        service, _ = _service()

        with pytest.raises(AlbumNotFoundError):
            service.view_of(99)


@pytest.mark.django_db
class TestReorder:
    def test_roots(self) -> None:
        service, albums = _service()
        first, second, third = (albums.add(name) for name in ("A", "B", "C"))

        service.reorder(SiblingOrder(parent_id=None, ids=[third, first, second]))

        assert [album.id for album in service.list_albums()] == [third, first, second]

    @pytest.mark.parametrize(
        ("ids_of", "field"),
        [
            (lambda a, b, other: [a], "missing"),
            (lambda a, b, other: [a, b, other], "unexpected"),
            (lambda a, b, other: [a, b, 999], "unexpected"),
            (lambda a, b, other: [a, b, a], "repeated"),
        ],
    )
    def test_mismatch_changes_nothing(self, ids_of: object, field: str) -> None:
        service, albums = _service()
        parent = albums.add("Retiros")
        first = albums.add("A", parent_id=parent)
        second = albums.add("B", parent_id=parent)
        other = albums.add("Outro")
        ids = ids_of(first, second, other)  # type: ignore[operator]

        with pytest.raises(OrderMismatchError) as caught:
            service.reorder(SiblingOrder(parent_id=parent, ids=ids))

        assert getattr(caught.value, field)
        assert albums.child_ids(parent) == [first, second]

    def test_unknown_parent(self) -> None:
        service, _ = _service()

        with pytest.raises(AlbumNotFoundError):
            service.reorder(SiblingOrder(parent_id=99, ids=[]))
