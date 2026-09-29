from uuid import uuid4

from django.conf import settings
from django.db import models

from features.gallery.domain.trash_rules import TrashedItemKind

_KIND_CHOICES = [(kind.value, kind.value) for kind in TrashedItemKind]


class GalleryDeletionBatch(models.Model):
    """Everything one delete action sent to the trash. Restoring its root restores exactly these
    rows; the purge removes them together (specs/014-gallery-trash-sync research R-01)."""

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    root_kind = models.CharField(max_length=5, choices=_KIND_CHOICES)
    # No FK: the batch and its root would reference each other, making the purge order circular.
    root_id = models.PositiveIntegerField()
    deleted_at = models.DateTimeField(db_index=True)
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    class Meta:
        ordering = ["-deleted_at", "id"]
        verbose_name = "gallery deletion batch"
        verbose_name_plural = "gallery deletion batches"
        constraints = [
            models.UniqueConstraint(
                fields=["root_kind", "root_id"], name="unique_gallery_deletion_batch_root"
            )
        ]

    def __str__(self) -> str:
        return f"{self.root_kind} {self.root_id} @ {self.deleted_at:%Y-%m-%d %H:%M}"


class GalleryDeletionMark(models.Model):
    """A deleted album or photo id the change feed still reports. No FK: it must outlive the
    purge of its row, for 90 days from the deletion (research R-08)."""

    kind = models.CharField(max_length=5, choices=_KIND_CHOICES)
    object_id = models.PositiveIntegerField()
    deleted_at = models.DateTimeField(db_index=True)

    class Meta:
        ordering = ["deleted_at", "id"]
        verbose_name = "gallery deletion mark"
        verbose_name_plural = "gallery deletion marks"
        constraints = [
            models.UniqueConstraint(
                fields=["kind", "object_id"], name="unique_gallery_deletion_mark"
            )
        ]

    def __str__(self) -> str:
        return f"{self.kind} {self.object_id} deleted {self.deleted_at:%Y-%m-%d}"
