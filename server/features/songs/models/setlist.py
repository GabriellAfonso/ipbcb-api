"""The Sunday setlist: what the worship ministry *will* play (specs/017-sunday-setlist-push).

``Played`` stays the record of what *was* played; a ``Played`` row for the date is what stops the
Sunday-night reminder. The date is always a Sunday, checked by the service rather than the
database: SQLite and PostgreSQL disagree on weekday functions, and the error must name the
weekday it got.
"""

from django.conf import settings
from django.db import models
from django.db.models import Q

from features.songs.models.song import Song

MIN_POSITION = 1
# Same ceiling as the played register: special occasions run past the usual four songs.
MAX_POSITION = 10


class Setlist(models.Model):
    date = models.DateField()
    saved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    saved_at = models.DateTimeField()
    # Start of the last reminder window claimed, before its push is sent. A re-save never
    # resets it: a correction at 22:10 must not repeat the 21:00-22:00 reminders (R-08, R-10).
    last_reminder_slot = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-date"]
        verbose_name = "setlist"
        verbose_name_plural = "setlists"
        constraints = [models.UniqueConstraint(fields=["date"], name="setlist_date_unique")]

    def __str__(self) -> str:
        return f"Setlist {self.date.isoformat()}"


class SetlistItem(models.Model):
    setlist = models.ForeignKey(Setlist, on_delete=models.CASCADE, related_name="items")
    position = models.PositiveSmallIntegerField()
    # PROTECT, like Played: a song a setlist points at cannot vanish from under it.
    song = models.ForeignKey(Song, on_delete=models.PROTECT, related_name="setlist_items")
    tone = models.CharField(max_length=3)

    class Meta:
        ordering = ["setlist", "position"]
        verbose_name = "setlist item"
        verbose_name_plural = "setlist items"
        constraints = [
            models.UniqueConstraint(
                fields=["setlist", "position"], name="setlist_item_position_unique"
            ),
            models.CheckConstraint(
                condition=Q(position__gte=MIN_POSITION) & Q(position__lte=MAX_POSITION),
                name="setlist_item_position_range",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.setlist.date.isoformat()} #{self.position} {self.song.title}"
