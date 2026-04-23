from django.db import models

from .song import Song


class Lyrics(models.Model):
    song = models.OneToOneField(Song, on_delete=models.CASCADE, related_name="lyrics")
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"Lyrics — {self.song.title}"
