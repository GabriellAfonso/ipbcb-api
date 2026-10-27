"""YouTube videos linked to Bible chapters and books (specs/025-bible-videos data-model).

A video exists only while it has a place; the service deletes it with its last place.
"""

from django.conf import settings
from django.db import models
from django.db.models import Q

from features.bible.domain.youtube_links import YouTubeKind

BOOK_MAX_LENGTH = 8
TITLE_MAX_LENGTH = 300
THUMBNAIL_URL_MAX_LENGTH = 500


class BibleVideo(models.Model):
    kind = models.CharField(
        max_length=10, choices=[(kind.value, kind.value) for kind in YouTubeKind]
    )
    youtube_id = models.CharField(max_length=64)
    # Canonical URL built by the server, so the same video pasted two ways is one row.
    url = models.CharField(max_length=300)
    # Read from YouTube once, on save; never edited nor refreshed.
    title = models.CharField(max_length=TITLE_MAX_LENGTH)
    thumbnail_url = models.CharField(max_length=THUMBNAIL_URL_MAX_LENGTH)
    # Auditing only; deleting the account keeps the video.
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["id"]
        verbose_name = "bible video"
        verbose_name_plural = "bible videos"
        constraints = [
            models.UniqueConstraint(
                fields=["kind", "youtube_id"], name="bible_video_unique_youtube_target"
            ),
        ]

    def __str__(self) -> str:
        return self.title


class BibleVideoPlace(models.Model):
    video = models.ForeignKey(BibleVideo, on_delete=models.CASCADE, related_name="places")
    book = models.CharField(max_length=BOOK_MAX_LENGTH)
    # NULL = the whole book.
    chapter = models.PositiveSmallIntegerField(null=True, blank=True)
    # Manual order inside (book, chapter), from 0. Ties are broken by video id.
    position = models.PositiveIntegerField()

    class Meta:
        ordering = ["book", "chapter", "position", "video_id"]
        verbose_name = "bible video place"
        verbose_name_plural = "bible video places"
        # SQL treats NULLs as distinct, so the whole-book place needs its own constraint.
        constraints = [
            models.UniqueConstraint(
                fields=["video", "book", "chapter"],
                condition=Q(chapter__isnull=False),
                name="bible_place_unique_chapter",
            ),
            models.UniqueConstraint(
                fields=["video", "book"],
                condition=Q(chapter__isnull=True),
                name="bible_place_unique_book",
            ),
        ]
        indexes = [
            models.Index(fields=["book", "chapter", "position"], name="bible_place_order_idx"),
        ]

    def __str__(self) -> str:
        chapter = "*" if self.chapter is None else self.chapter
        return f"{self.book} {chapter} #{self.position}"
