from typing import Any
from uuid import uuid4

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

from features.gallery.models.trash import GalleryDeletionBatch

# Hiding trashed rows is the default on purpose: the feature exists so that deleted photos stop
# being visible, and a forgotten filter would show one silently. Every 013 query, the reverse
# relations, the admin and its choice fields get live rows only; code that needs trashed rows
# asks for them by name through `all_objects` (specs/014-gallery-trash-sync research R-02).
_LIVE = Q(deleted_at__isnull=True)
_TRASHED = Q(deleted_at__isnull=False)


class LiveAlbumManager(models.Manager["Album"]):
    def get_queryset(self) -> models.QuerySet["Album"]:
        return super().get_queryset().filter(_LIVE)


class LivePhotoManager(models.Manager["Photo"]):
    def get_queryset(self) -> models.QuerySet["Photo"]:
        return super().get_queryset().filter(_LIVE)


def cover_upload_path(instance: Any, filename: str) -> str:
    """Fallback path for a cover saved straight through the field; the service names covers
    itself through ``GalleryFileStorage``."""
    return f"gallery/covers/{instance.pk}/{uuid4().hex}.jpg"


class Album(models.Model):
    name = models.CharField(max_length=100)
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="children"
    )
    description = models.TextField(blank=True, default="")
    event_date = models.DateField(null=True, blank=True)
    position = models.PositiveIntegerField(default=0)
    cover_image = models.ImageField(upload_to=cover_upload_path, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    deletion_batch = models.ForeignKey(
        GalleryDeletionBatch,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="albums",
    )
    # Set explicitly by every write, derived changes included; `auto_now` would miss the
    # `QuerySet.update()` calls the repositories use (research R-06).
    updated_at = models.DateTimeField(default=timezone.now, db_index=True)

    objects = LiveAlbumManager()
    all_objects = models.Manager()

    class Meta:
        ordering = ["position", "id"]
        verbose_name = "album"
        verbose_name_plural = "albums"
        # Two constraints because SQL NULLs are distinct: a single (parent, name) constraint
        # would let any number of roots share a name (specs/013-gallery-write-api R-01). Live
        # rows only: a trashed album never holds its name (specs/014-gallery-trash-sync FR-010).
        constraints = [
            models.UniqueConstraint(
                fields=["parent", "name"],
                condition=Q(parent__isnull=False) & _LIVE,
                name="unique_live_album_name_per_parent",
            ),
            models.UniqueConstraint(
                fields=["name"],
                condition=Q(parent__isnull=True) & _LIVE,
                name="unique_live_root_album_name",
            ),
        ]
        indexes = [
            models.Index(fields=["parent", "position"], name="album_parent_position"),
            # Partial: only trashed rows, so the media check's lookup stays tiny (research R-05).
            models.Index(fields=["cover_image"], condition=_TRASHED, name="album_trashed_cover"),
        ]

    def __str__(self) -> str:
        return self.name


def photo_upload_path(instance: Any, filename: str) -> str:
    """Fallback path for a photo saved straight through the field.

    Kept importable because ``0001_initial`` references it by dotted path. Uploads go through
    ``GalleryFileStorage``, which names the file before the row exists; the extension there
    comes from the decoded format, never from ``filename``.
    """
    extension = filename.rpartition(".")[2].lower() or "jpg"
    return f"gallery/{instance.album_id}/{uuid4().hex}.{extension}"


def thumbnail_upload_path(instance: Any, filename: str) -> str:
    """Fallback path for a thumbnail saved straight through the field."""
    return f"gallery/thumbs/{instance.album_id}/{uuid4().hex}.jpg"


class Photo(models.Model):
    # PROTECT: an album row must never take photo rows with it. Only the purge deletes rows, and
    # always with their files; with CASCADE, a photo whose own purge failed would vanish with its
    # album and orphan its files (specs/014-gallery-trash-sync research R-09).
    album = models.ForeignKey(Album, related_name="photos", on_delete=models.PROTECT)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to=photo_upload_path)
    thumbnail = models.ImageField(upload_to=thumbnail_upload_path, blank=True)
    date_taken = models.DateField(blank=True, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    # Auditing only: never part of the photo resource members read.
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    position = models.PositiveIntegerField(default=0)
    deleted_at = models.DateTimeField(null=True, blank=True)
    deletion_batch = models.ForeignKey(
        GalleryDeletionBatch,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="photos",
    )
    updated_at = models.DateTimeField(default=timezone.now, db_index=True)

    objects = LivePhotoManager()
    all_objects = models.Manager()

    class Meta:
        ordering = ["position", "id"]
        verbose_name = "photo"
        verbose_name_plural = "photos"
        indexes = [
            models.Index(fields=["album", "position"], name="photo_album_position"),
            models.Index(fields=["image"], condition=_TRASHED, name="photo_trashed_image"),
            models.Index(fields=["thumbnail"], condition=_TRASHED, name="photo_trashed_thumbnail"),
        ]

    def __str__(self) -> str:
        return self.name
