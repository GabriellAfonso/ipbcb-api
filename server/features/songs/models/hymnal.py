from django.db import models


class Hymn(models.Model):
    number = models.CharField(max_length=10, unique=True)  # agora aceita 110-A
    title = models.CharField(max_length=200)
    lyrics = models.JSONField()

    def __str__(self):
        return f"{self.number} - {self.title}"
