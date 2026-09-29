from features.gallery.services.photo_ordering import order_photos_by_tree
from features.gallery.tests.fakes import FakeAlbumRepository, FakeGalleryRepository


def test_photos_follow_the_album_tree_then_their_own_order() -> None:
    albums = FakeAlbumRepository()
    photos = FakeGalleryRepository(albums)
    second_root = albums.add("B")
    first_root = albums.add("A")
    albums.apply_order([first_root, second_root])
    child = albums.add("A1", parent_id=first_root)
    in_second, in_child, in_first = (photos.add(a) for a in (second_root, child, first_root))

    ordered = order_photos_by_tree(photos.list_all_photos(), albums.list_records())

    assert [p.id for p in ordered] == [in_first, in_child, in_second]


def test_photo_of_an_unknown_album_goes_last() -> None:
    albums = FakeAlbumRepository()
    photos = FakeGalleryRepository(albums)
    album = albums.add("A")
    photo = photos.add(album)

    assert [p.id for p in order_photos_by_tree(photos.list_all_photos(), [])] == [photo]
