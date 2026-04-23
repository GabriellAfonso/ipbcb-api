from typing import Any

from django.db import models
from django.utils.text import slugify


class Album(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self) -> str:
        return self.name


def photo_upload_path(instance: Any, filename: str) -> str:
    album_slug = slugify(instance.album.name)
    return f"gallery/{album_slug}/{filename}"


class Photo(models.Model):
    album = models.ForeignKey(Album, related_name="photos", on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to=photo_upload_path)
    date_taken = models.DateField(blank=True, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return self.name
