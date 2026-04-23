from typing import Any

from django.db import models
from django.utils import timezone

from features.members.models.member import Member


class ScheduleType(models.Model):
    name = models.CharField(max_length=100)
    weekday = models.PositiveSmallIntegerField()
    time = models.TimeField()

    def __str__(self) -> str:
        return f"{self.name} - {self.id}"


class MemberScheduleConfig(models.Model):
    member = models.ForeignKey(Member, on_delete=models.CASCADE)
    schedule_type = models.ForeignKey(ScheduleType, on_delete=models.CASCADE)
    available = models.BooleanField(default=True)
    weight = models.PositiveIntegerField(default=1)

    class Meta:
        unique_together = ("member", "schedule_type")

    def __str__(self) -> str:
        return f"{self.member.name} - {self.schedule_type.name}"


class MonthlySchedule(models.Model):
    year = models.PositiveIntegerField(editable=False)
    month = models.PositiveSmallIntegerField(editable=False)

    date = models.DateField()
    schedule_type = models.ForeignKey(ScheduleType, on_delete=models.CASCADE)
    member = models.ForeignKey(Member, on_delete=models.PROTECT)
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        unique_together = ("schedule_type", "date")

    def save(self, *args: Any, **kwargs: Any) -> None:
        if self.date:
            self.year = self.date.year
            self.month = self.date.month
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.member.name} - {self.date.strftime('%d/%m/%Y')} - {self.schedule_type.name}"
