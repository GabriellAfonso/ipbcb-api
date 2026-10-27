"""Per-account reading and watching progress (specs/025-bible-videos data-model).

``done=False`` rows are kept as tombstones: last-write-wins needs to remember when something was
unmarked, or an older offline "mark" from another device would bring it back.
"""

from django.conf import settings
from django.db import models

from features.bible.models.bible_video import BOOK_MAX_LENGTH, BibleVideo


class BibleChapterProgress(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    book = models.CharField(max_length=BOOK_MAX_LENGTH)
    chapter = models.PositiveSmallIntegerField()
    done = models.BooleanField()
    # Device time of the change (UTC); decides conflicts, not arrival order.
    changed_at = models.DateTimeField()

    class Meta:
        ordering = ["user_id", "book", "chapter"]
        verbose_name = "bible chapter progress"
        verbose_name_plural = "bible chapter progress"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "book", "chapter"], name="bible_chapter_progress_unique"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.book} {self.chapter} {'done' if self.done else 'not done'}"


class BibleVideoProgress(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    video = models.ForeignKey(BibleVideo, on_delete=models.CASCADE, related_name="+")
    done = models.BooleanField()
    changed_at = models.DateTimeField()

    class Meta:
        ordering = ["user_id", "video_id"]
        verbose_name = "bible video progress"
        verbose_name_plural = "bible video progress"
        constraints = [
            models.UniqueConstraint(fields=["user", "video"], name="bible_video_progress_unique"),
        ]

    def __str__(self) -> str:
        return f"video {self.video_id} {'done' if self.done else 'not done'}"
