"""A church event shown in the app's home carousel (specs/020-church-events).

Whether an event is active or past is never stored: it is a filter on the last day, computed
per request in São Paulo time, so nothing has to run at midnight.
"""

from django.conf import settings
from django.db import models
from django.db.models import F, Q

from features.events.domain.event_enums import EventVisibility

TITLE_MAX_LENGTH = 120
LOCATION_MAX_LENGTH = 200


class Event(models.Model):
    title = models.CharField(max_length=TITLE_MAX_LENGTH)
    start_date = models.DateField(db_index=True)
    end_date = models.DateField(null=True, blank=True)
    start_time = models.TimeField(null=True, blank=True)
    # NULL, never "", when absent: the app reads null for every missing optional value.
    location = models.CharField(max_length=LOCATION_MAX_LENGTH, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    # Storage name, e.g. "events/8c41….jpg". Unique, hence indexed: the media check looks the
    # file's event up by it (research R-05). A plain column so Django never touches the file.
    image_path = models.CharField(max_length=255, unique=True)
    visibility = models.CharField(
        max_length=10,
        choices=[(visibility.value, visibility.value) for visibility in EventVisibility],
        default=EventVisibility.PUBLIC.value,
    )
    # Auditing: shown to the panel, never to the public.
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
        ordering = ["-start_date", "-id"]
        verbose_name = "event"
        verbose_name_plural = "events"
        constraints = [
            models.CheckConstraint(
                condition=Q(end_date__isnull=True) | Q(end_date__gte=F("start_date")),
                name="event_end_not_before_start",
            ),
        ]

    def __str__(self) -> str:
        return self.title
