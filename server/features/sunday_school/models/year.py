"""A year of Sunday school lessons and its theme (specs/026-sunday-school data-model)."""

from django.db import models

THEME_MAX_LENGTH = 200


class SundaySchoolYear(models.Model):
    # Created implicitly when a lesson is saved for it; never deleted through the API.
    year = models.PositiveSmallIntegerField(unique=True)
    # Blank when the year has no theme. One place, so it is never repeated on each lesson.
    theme = models.CharField(max_length=THEME_MAX_LENGTH, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-year"]
        verbose_name = "sunday school year"
        verbose_name_plural = "sunday school years"

    def __str__(self) -> str:
        return f"{self.year} — {self.theme}" if self.theme else str(self.year)
