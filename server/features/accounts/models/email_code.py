from django.db import models

from features.accounts.domain.email_codes import EmailCodePurpose
from features.accounts.models.user import User


class EmailCode(models.Model):
    """A code that can still be used: consuming or invalidating one deletes its row
    (specs/028-password-recovery data-model). Not in the Django admin."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="+")
    purpose = models.CharField(
        max_length=12, choices=[(purpose.value, purpose.value) for purpose in EmailCodePurpose]
    )
    address = models.EmailField()
    code_digest = models.CharField(max_length=64)
    # For recovery this is the count of the whole address: every live row of an address comes from
    # one request and is incremented together (research R-01), so accounts sharing an address do
    # not multiply the guesses.
    failed_attempts = models.PositiveSmallIntegerField(default=0)
    expires_at = models.DateTimeField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        verbose_name = "e-mail code"
        verbose_name_plural = "e-mail codes"
        constraints = [
            models.UniqueConstraint(fields=["user", "purpose"], name="unique_email_code_per_user")
        ]
        indexes = [models.Index(fields=["purpose", "address"], name="email_code_address_idx")]

    def __str__(self) -> str:
        # Names the row only: never the address or the digest.
        return f"{self.purpose} code of user {self.user_id}"


class EmailSendLedger(models.Model):
    """When an address last received messages, for the per-address limit. One row per address, so
    it can be locked even for the first send, and keyed by a hash so anonymous input is not stored
    readable (research R-03, R-04)."""

    address_key = models.CharField(max_length=64, unique=True)
    # ISO instants inside the last hour.
    send_times = models.JSONField(default=list)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)

    class Meta:
        ordering = ["updated_at"]
        verbose_name = "e-mail send ledger"
        verbose_name_plural = "e-mail send ledgers"

    def __str__(self) -> str:
        return f"send ledger {self.address_key[:8]}"
