from django.db import models


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self) -> str:
        return self.name


class Song(models.Model):
    title = models.CharField(max_length=100)
    artist = models.CharField(max_length=100)
    category = models.ForeignKey(Category, null=True, blank=True, on_delete=models.SET_NULL)

    def __str__(self) -> str:
        return f"{self.title} ------- {self.artist}"


class Played(models.Model):
    song = models.ForeignKey(
        Song, null=True, blank=True, on_delete=models.PROTECT, related_name="plays"
    )
    tone = models.CharField(max_length=3)
    position = models.IntegerField()
    date = models.DateField()

    def __str__(self) -> str:
        title = self.song.title if self.song else "?"
        return f"{title} ------- {self.date.strftime('%d/%m/%Y')}"
