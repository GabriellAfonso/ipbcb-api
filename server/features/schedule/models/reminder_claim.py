from django.db import models
from django.utils import timezone


class ScheduleReminderClaim(models.Model):
    """That one rota reminder was claimed for one member and one occasion, before its push went
    out (specs/024-schedule-reminders R-01, R-02).

    ``occasion`` is a string key whose shape depends on ``kind``: the Monday (``2026-10-26``) for
    the week summary, ``date/service id`` (``2026-10-29/3``) for an eve reminder, ``YYYY-MM`` for
    the publication. ``run_id`` tells a run which of its bulk-inserted rows it actually won.
    """

    class Kind(models.TextChoices):
        WEEK = "schedule_week"
        EVE = "schedule_eve"
        PUBLISHED = "schedule_published"

    kind = models.CharField(max_length=20, choices=Kind.choices)
    # CASCADE: a claim is bookkeeping, not history. The rota row itself PROTECTs the member.
    member = models.ForeignKey("members.Member", on_delete=models.CASCADE)
    occasion = models.CharField(max_length=32)
    run_id = models.UUIDField()
    claimed_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-claimed_at"]
        verbose_name = "schedule reminder claim"
        constraints = [
            models.UniqueConstraint(
                fields=["kind", "member", "occasion"], name="unique_schedule_reminder_claim"
            )
        ]

    def __str__(self) -> str:
        # Ids only: the member's name is roll data (constitution, Security).
        return f"{self.kind} {self.occasion} member={self.member_id}"
