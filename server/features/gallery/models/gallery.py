from typing import Any
from uuid import uuid4

from django.conf import settings
from django.db import models
from django.db.models import Q


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

    class Meta:
        ordering = ["position", "id"]
        verbose_name = "album"
        verbose_name_plural = "albums"
        # Two constraints because SQL NULLs are distinct: a single (parent, name) constraint
        # would let any number of roots share a name (specs/013-gallery-write-api R-01).
        constraints = [
            models.UniqueConstraint(
                fields=["parent", "name"],
                condition=Q(parent__isnull=False),
                name="unique_album_name_per_parent",
            ),
            models.UniqueConstraint(
                fields=["name"],
                condition=Q(parent__isnull=True),
                name="unique_root_album_name",
            ),
        ]
        indexes = [models.Index(fields=["parent", "position"], name="album_parent_position")]

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
    album = models.ForeignKey(Album, related_name="photos", on_delete=models.CASCADE)
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

    class Meta:
        ordering = ["position", "id"]
        verbose_name = "photo"
        verbose_name_plural = "photos"
        indexes = [models.Index(fields=["album", "position"], name="photo_album_position")]

    def __str__(self) -> str:
        return self.name
