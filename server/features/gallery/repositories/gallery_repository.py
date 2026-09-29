from collections.abc import Iterator, Mapping, Sequence

from django.db import transaction
from django.db.models import Max, QuerySet

from features.gallery.dtos.gallery_dtos import NewPhoto, PhotoView
from features.gallery.models.gallery import Album, Photo


class GalleryRepositoryImpl:
    """Gallery photos through the Django ORM."""

    def list_all_photos(self) -> list[PhotoView]:
        """Every photo by position within its album; the service orders albums by tree."""
        return [_to_view(photo) for photo in _photos()]

    def list_photos_by_album(self, album_id: int) -> list[PhotoView]:
        return [_to_view(photo) for photo in _photos().filter(album_id=album_id)]

    def get_photo(self, photo_id: int) -> PhotoView | None:
        photo = _photos().filter(pk=photo_id).first()
        return _to_view(photo) if photo else None

    def create_photo(self, photo: NewPhoto) -> PhotoView:
        """Insert the row last in its album. The files are already stored."""
        with transaction.atomic():
            created = Photo.objects.create(
                album_id=photo.album_id,
                image=photo.image_name,
                thumbnail=photo.thumbnail_name,
                name=photo.name,
                date_taken=photo.date_taken,
                uploaded_by_id=photo.uploader_id,
                position=_next_photo_position(photo.album_id),
            )
        return _to_view(_photos().get(pk=created.pk))

    def update_photo(self, photo_id: int, fields: Mapping[str, object]) -> None:
        Photo.objects.filter(pk=photo_id).update(**fields)

    def move_photo(self, photo_id: int, album_id: int) -> None:
        with transaction.atomic():
            position = _next_photo_position(album_id)
            Photo.objects.filter(pk=photo_id).update(album_id=album_id, position=position)

    def photo_ids(self, album_id: int) -> list[int]:
        return list(Photo.objects.filter(album_id=album_id).values_list("id", flat=True))

    def apply_order(self, ids: Sequence[int]) -> None:
        photos = [Photo(pk=photo_id, position=index) for index, photo_id in enumerate(ids)]
        with transaction.atomic():
            Photo.objects.bulk_update(photos, ["position"])

    def photos_without_thumbnail(self) -> Iterator[tuple[int, int, str]]:
        """(id, album id, original name) of each photo lacking a thumbnail, read in batches."""
        rows = (
            Photo.objects.filter(thumbnail="").order_by("id").values_list("id", "album_id", "image")
        )
        yield from rows.iterator(chunk_size=100)

    def set_thumbnail(self, photo_id: int, name: str) -> None:
        Photo.objects.filter(pk=photo_id).update(thumbnail=name)


def _photos() -> QuerySet[Photo]:
    return Photo.objects.select_related("album").order_by("position", "id")


def _next_photo_position(album_id: int) -> int:
    """Lock the album row so concurrent appends into it serialize, then take the next slot."""
    list(Album.objects.select_for_update().filter(pk=album_id).values_list("pk"))
    last = Photo.objects.filter(album_id=album_id).aggregate(last=Max("position"))["last"]
    return 0 if last is None else last + 1


def _to_view(photo: Photo) -> PhotoView:
    return PhotoView(
        id=photo.pk,
        name=photo.name,
        description=photo.description,
        album_id=photo.album_id,
        album_name=photo.album.name,
        image_path=photo.image.url if photo.image else None,
        thumbnail_path=photo.thumbnail.url if photo.thumbnail else None,
        date_taken=photo.date_taken,
        uploaded_at=photo.uploaded_at,
    )
