from django.db import models

from features.songs.models.song import Song


class ChordChart(models.Model):
    song = models.ForeignKey(Song, on_delete=models.CASCADE, related_name="chord_charts")
    content = models.TextField()
    tone = models.CharField(max_length=3, blank=True)
    instrument = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("song", "tone", "instrument")

    def __str__(self) -> str:
        parts = [self.song.title]
        if self.tone:
            parts.append(self.tone)
        if self.instrument:
            parts.append(self.instrument)
        return f"Chord Chart — {' | '.join(parts)}"
