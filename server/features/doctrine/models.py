"""A Westminster Standard stored as one row (specs/027-doctrine-database data-model).

Rows are written only by data migrations; there is no write endpoint and no admin registration,
because doctrine is never edited (spec FR-007).
"""

from django.db import models

KIND_CHOICES = [("catechism", "catechism"), ("confession", "confession")]


class DoctrineStandard(models.Model):
    slug = models.SlugField(max_length=100, unique=True)
    title = models.CharField(max_length=200)
    kind = models.CharField(max_length=10, choices=KIND_CHOICES)
    position = models.PositiveSmallIntegerField(unique=True)
    # Where the text comes from, e.g. "Edição IPB"; "" while unknown, served as null.
    edition = models.CharField(max_length=120, blank=True)
    year = models.PositiveSmallIntegerField(null=True, blank=True)
    # The validated ``questions`` (catechism) or ``chapters`` (confession) list, stored with
    # unset keys left out so a paragraph without a list keeps only number and text (R-02).
    content = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["position"]
        verbose_name = "doctrine document"
        verbose_name_plural = "doctrine documents"

    def __str__(self) -> str:
        return self.title
