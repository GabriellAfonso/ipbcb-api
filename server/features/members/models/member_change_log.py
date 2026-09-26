from django.conf import settings
from django.db import models

from features.members.models.member import Member


class MemberChangeLog(models.Model):
    """One change to one field of one member, made by a leader through the service layer.

    Written by the services in the same transaction as the change, never by signals: a
    signal does not know the editor. Values are stored as display text (see
    ``features.members.domain.member_changes``) so an entry reads "X changed F from A to B"
    even after the referenced status or ministry is renamed.
    """

    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name="change_log")
    # SET_NULL: the history outlives the editor's account. "+" keeps accounts.User free of a
    # reverse accessor into this feature.
    editor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )
    field = models.CharField(max_length=32)
    old_value = models.TextField(null=True)
    new_value = models.TextField(null=True)
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-changed_at", "-id"]
        verbose_name = "member change log entry"
        verbose_name_plural = "member change log"

    def __str__(self) -> str:
        # Ids only: member names are sensitive data and __str__ ends up in logs and admin.
        return f"member {self.member_id}: {self.field} at {self.changed_at}"
