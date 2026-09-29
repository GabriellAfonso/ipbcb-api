from django.conf import settings
from django.db import models
from django.utils import timezone

from features.gallery.models.gallery import Photo


class PhotoTag(models.Model):
    """A member who appears in a photo (specs/015-gallery-member-tags).

    CASCADE on both sides: the 014 purge removes a photo's tags with its row, and deleting a
    member removes theirs; a trashed photo keeps its row, so its tags wait with it. The member is
    referenced by name, as ``features/schedule`` does, so the gallery never imports the members
    feature, and ``related_name="+"`` keeps ``Member`` free of an accessor into the gallery.
    """

    photo = models.ForeignKey(Photo, on_delete=models.CASCADE, related_name="tags")
    member = models.ForeignKey("members.Member", on_delete=models.CASCADE, related_name="+")
    # Auditing only: never part of any resource (spec FR-010).
    tagged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    tagged_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["photo_id", "member_id"]
        verbose_name = "photo tag"
        verbose_name_plural = "photo tags"
        constraints = [
            models.UniqueConstraint(fields=["photo", "member"], name="unique_photo_tag"),
        ]

    def __str__(self) -> str:
        # Ids only: a tag ties a named person to a church photo (constitution, sensitive data).
        return f"{self.photo_id}:{self.member_id}"
