"""A request an account makes to the church leadership (specs/022-access-requests): member access,
or a correction of its record on the roll."""

from django.conf import settings
from django.db import models
from django.db.models import Q

from features.accounts.domain.access_requests import AccessRequestStatus, AccessRequestType


class AccessRequest(models.Model):
    # CASCADE: the request is the account's own data and goes with it (spec FR-024).
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="access_requests"
    )
    type = models.CharField(
        max_length=20, choices=[(kind.value, kind.value) for kind in AccessRequestType]
    )
    message = models.TextField(null=True, blank=True)
    status = models.CharField(
        max_length=10,
        choices=[(state.value, state.value) for state in AccessRequestStatus],
        default=AccessRequestStatus.PENDING.value,
        db_index=True,
    )
    # SET_NULL: deleting the leader's account keeps the decision (spec FR-024).
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    denial_reason = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        verbose_name = "access request"
        verbose_name_plural = "access requests"
        constraints = [
            # Closes the race between the service's "already pending?" check and the insert.
            models.UniqueConstraint(
                fields=["user", "type"],
                condition=Q(status=AccessRequestStatus.PENDING.value),
                name="access_request_one_pending_per_type",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.type} ({self.status})"
