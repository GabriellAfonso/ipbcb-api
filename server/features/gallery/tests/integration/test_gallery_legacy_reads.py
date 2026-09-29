"""App versions released before feature 013 keep working: the existing reads lose nothing
(specs/013-gallery-write-api SC-006, quickstart §2; specs/014-gallery-trash-sync SC-007)."""

import pytest

from conftest import make_member_client
from features.gallery.models.gallery import Album, Photo

LEGACY_FIELDS = {
    "id",
    "name",
    "description",
    "album_id",
    "album_name",
    "image_url",
    "date_taken",
    "uploaded_at",
}


@pytest.mark.django_db
class TestLegacyReads:
    @pytest.mark.parametrize("url", ["/api/photos/", "/api/albums/{album}/photos/"])
    def test_every_old_field_is_kept_and_only_new_fields_are_added(self, url: str) -> None:
        album = Album.objects.create(name="Culto")
        Photo.objects.create(album=album, name="foto.jpg", image="gallery/culto/foto.jpg")

        client, _ = make_member_client()
        photo = client.get(url.format(album=album.pk)).data[0]

        # thumbnail_url by 013, position by 014, members (last) by 015.
        assert set(photo) == LEGACY_FIELDS | {"thumbnail_url", "position", "members"}
        assert list(photo)[-2:] == ["position", "members"]
        assert photo["members"] == []
        assert list(photo)[:6] == [
            "id",
            "name",
            "description",
            "album_id",
            "album_name",
            "image_url",
        ]

    def test_the_feed_carries_members_too(self) -> None:
        album = Album.objects.create(name="Culto")
        Photo.objects.create(album=album, name="foto.jpg", image="gallery/culto/foto.jpg")

        client, _ = make_member_client()
        photo = client.get("/api/gallery/changes/").data["photos"][0]

        assert list(photo)[-1] == "members"

    def test_a_photo_stored_under_the_old_path_keeps_its_url(self) -> None:
        album = Album.objects.create(name="Culto")
        Photo.objects.create(album=album, name="IMG_0042.jpg", image="gallery/culto/IMG_0042.jpg")

        client, _ = make_member_client()
        photo = client.get("/api/photos/").data[0]

        assert photo["image_url"].endswith("/ipbcb/media/gallery/culto/IMG_0042.jpg")
        assert photo["thumbnail_url"] is None
