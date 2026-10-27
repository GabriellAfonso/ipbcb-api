"""A Sunday school lesson (specs/026-sunday-school data-model)."""

from django.conf import settings
from django.db import models

from features.sunday_school.domain.lesson_status import LessonStatus
from features.sunday_school.models.year import SundaySchoolYear

TITLE_MAX_LENGTH = 200
TEACHER_MAX_LENGTH = 120


class SundaySchoolLesson(models.Model):
    year = models.ForeignKey(SundaySchoolYear, on_delete=models.PROTECT, related_name="lessons")
    title = models.CharField(max_length=TITLE_MAX_LENGTH)
    # Many lessons have no known date, which is why the year is a separate field.
    date = models.DateField(null=True, blank=True)
    # Free text: the name of whoever gave it, when known; not a link to the church roll.
    teacher = models.CharField(max_length=TEACHER_MAX_LENGTH, blank=True)
    status = models.CharField(
        max_length=10, choices=[(status.value, status.value) for status in LessonStatus]
    )
    # Order inside the year, 0..n-1. No unique constraint: renumbering would depend on update
    # order; ties are ordered by id (research R-07).
    position = models.PositiveIntegerField()
    # The validated, normalized LessonContent document.
    content = models.JSONField()
    # Auditing only; deleting the account keeps the lesson. Null on imported lessons.
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["year__year", "position", "id"]
        verbose_name = "sunday school lesson"
        verbose_name_plural = "sunday school lessons"
        indexes = [
            models.Index(fields=["year", "status", "position"], name="sunday_lesson_order_idx"),
        ]

    def __str__(self) -> str:
        return self.title
