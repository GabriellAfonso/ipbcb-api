from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from django.db import transaction
from django.db.models import F, QuerySet

from features.accounts.domain.email_codes import (
    MAX_WRONG_ATTEMPTS,
    SEND_WINDOW,
    EmailCodePurpose,
    send_wait_seconds,
    sends_inside_window,
)
from features.accounts.dtos import NewEmailCodeDTO, PendingEmailCodeDTO
from features.accounts.models.email_code import EmailCode, EmailSendLedger
from features.accounts.repositories.interfaces import EmailCodeRepository


def _pending(rows: QuerySet[EmailCode]) -> list[PendingEmailCodeDTO]:
    return [
        PendingEmailCodeDTO(user_id=row.user_id, code_digest=row.code_digest)
        for row in rows.select_for_update()
    ]


def _count_failure(rows: QuerySet[EmailCode]) -> None:
    rows.update(failed_attempts=F("failed_attempts") + 1)
    rows.filter(failed_attempts__gte=MAX_WRONG_ATTEMPTS).delete()


class EmailCodeRepositoryImpl(EmailCodeRepository):
    """Pending codes and the send ledger. Every ``lock_*`` and ``count_failure_*`` call must run
    inside the caller's transaction."""

    def claim_send_slot(self, key: str, now: datetime) -> int:
        """Record a send for this address and return 0, or return the seconds to wait and record
        nothing. ``get_or_create`` first so there is always a row to lock: concurrent requests for
        a new address cannot pass the check together (research R-03).

        >>> repo.claim_send_slot("9f2c...", now)
        0
        """
        with transaction.atomic():
            EmailSendLedger.objects.get_or_create(address_key=key)
            ledger = EmailSendLedger.objects.select_for_update().get(address_key=key)
            stored = [datetime.fromisoformat(moment) for moment in ledger.send_times]
            recent = sends_inside_window(stored, now)
            wait = send_wait_seconds(recent, now)
            if wait:
                return wait
            ledger.send_times = [moment.isoformat() for moment in [*recent, now]]
            ledger.save(update_fields=["send_times", "updated_at"])
        return 0

    def replace_codes(self, codes: Sequence[NewEmailCodeDTO]) -> None:
        """Store new codes, invalidating earlier ones of the same purpose for those accounts.

        >>> repo.replace_codes([NewEmailCodeDTO(...)])
        """
        with transaction.atomic():
            for purpose in {code.purpose for code in codes}:
                user_ids = [code.user_id for code in codes if code.purpose == purpose]
                EmailCode.objects.filter(purpose=purpose, user_id__in=user_ids).delete()
            EmailCode.objects.bulk_create(
                [
                    EmailCode(
                        user_id=code.user_id,
                        purpose=code.purpose,
                        address=code.address,
                        code_digest=code.code_digest,
                        expires_at=code.expires_at,
                    )
                    for code in codes
                ]
            )

    def lock_live_for_address(
        self, purpose: EmailCodePurpose, address: str, now: datetime
    ) -> list[PendingEmailCodeDTO]:
        """>>> repo.lock_live_for_address(EmailCodePurpose.RECOVERY, "ana@example.com", now)
        [PendingEmailCodeDTO(...)]
        """
        return _pending(
            EmailCode.objects.filter(purpose=purpose, address=address, expires_at__gt=now)
        )

    def lock_live_for_user(
        self, purpose: EmailCodePurpose, user_id: UUID, now: datetime
    ) -> list[PendingEmailCodeDTO]:
        """>>> repo.lock_live_for_user(EmailCodePurpose.CONFIRMATION, user.pk, now)
        [PendingEmailCodeDTO(...)]
        """
        return _pending(
            EmailCode.objects.filter(purpose=purpose, user_id=user_id, expires_at__gt=now)
        )

    def count_failure_for_address(self, purpose: EmailCodePurpose, address: str) -> None:
        """One wrong guess against every code of the address; the limit deletes them all.

        >>> repo.count_failure_for_address(EmailCodePurpose.RECOVERY, "ana@example.com")
        """
        _count_failure(EmailCode.objects.filter(purpose=purpose, address=address))

    def count_failure_for_user(self, purpose: EmailCodePurpose, user_id: UUID) -> None:
        """>>> repo.count_failure_for_user(EmailCodePurpose.CONFIRMATION, user.pk)"""
        _count_failure(EmailCode.objects.filter(purpose=purpose, user_id=user_id))

    def consume(self, purpose: EmailCodePurpose, user_id: UUID) -> None:
        """>>> repo.consume(EmailCodePurpose.RECOVERY, user.pk)"""
        EmailCode.objects.filter(purpose=purpose, user_id=user_id).delete()

    def delete_for_user(self, user_id: UUID) -> None:
        """Every pending code of the account, whatever the purpose: its address changed.

        >>> repo.delete_for_user(user.pk)
        """
        EmailCode.objects.filter(user_id=user_id).delete()

    def purge_expired(self, now: datetime) -> int:
        """Delete expired codes and ledgers with nothing left inside the window; return how many.
        Housekeeping only: expired rows are already ignored.

        >>> repo.purge_expired(now)
        3
        """
        codes, _ = EmailCode.objects.filter(expires_at__lte=now).delete()
        ledgers, _ = EmailSendLedger.objects.filter(updated_at__lte=now - SEND_WINDOW).delete()
        return codes + ledgers
