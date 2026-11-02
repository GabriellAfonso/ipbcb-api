"""EmailCodeRepositoryImpl and its cleanup command (specs/028-password-recovery)."""

from datetime import UTC, datetime, timedelta
from io import StringIO

import pytest
from axes.models import AccessAttempt
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.utils import timezone

from conftest import make_user
from features.accounts.domain.email_codes import EmailCodePurpose
from features.accounts.dtos import NewEmailCodeDTO
from features.accounts.models.email_code import EmailCode, EmailSendLedger
from features.accounts.models.user import User
from features.accounts.repositories.email_code_repository import EmailCodeRepositoryImpl
from features.accounts.repositories.lockout_resetter import AxesLockoutResetter
from features.accounts.repositories.user_repository import UserRepositoryImpl

NOW = datetime(2026, 11, 2, 12, 0, tzinfo=UTC)
ADDRESS = "ana@example.com"
RECOVERY = EmailCodePurpose.RECOVERY
CONFIRMATION = EmailCodePurpose.CONFIRMATION

pytestmark = pytest.mark.django_db


@pytest.fixture
def repo() -> EmailCodeRepositoryImpl:
    return EmailCodeRepositoryImpl()


def _code(
    user: User,
    purpose: EmailCodePurpose = RECOVERY,
    address: str = ADDRESS,
    expires_at: datetime = NOW + timedelta(minutes=15),
) -> NewEmailCodeDTO:
    return NewEmailCodeDTO(
        user_id=user.pk,
        purpose=purpose,
        address=address,
        code_digest="digest-" + user.username,
        expires_at=expires_at,
    )


def test_claim_records_a_send(repo: EmailCodeRepositoryImpl) -> None:
    assert repo.claim_send_slot("key", NOW) == 0

    assert EmailSendLedger.objects.get(address_key="key").send_times == [NOW.isoformat()]


def test_refused_claim_records_nothing(repo: EmailCodeRepositoryImpl) -> None:
    repo.claim_send_slot("key", NOW)

    assert repo.claim_send_slot("key", NOW + timedelta(seconds=10)) == 50

    assert len(EmailSendLedger.objects.get(address_key="key").send_times) == 1


def test_claims_of_different_addresses_are_independent(repo: EmailCodeRepositoryImpl) -> None:
    repo.claim_send_slot("key", NOW)

    assert repo.claim_send_slot("other", NOW) == 0


def test_claim_forgets_sends_older_than_the_window(repo: EmailCodeRepositoryImpl) -> None:
    repo.claim_send_slot("key", NOW)

    later = NOW + timedelta(hours=2)
    assert repo.claim_send_slot("key", later) == 0

    assert EmailSendLedger.objects.get(address_key="key").send_times == [later.isoformat()]


def test_six_spaced_claims_hit_the_hourly_limit(repo: EmailCodeRepositoryImpl) -> None:
    for minutes in range(0, 50, 10):
        assert repo.claim_send_slot("key", NOW + timedelta(minutes=minutes)) == 0

    assert repo.claim_send_slot("key", NOW + timedelta(minutes=50)) == 10 * 60


def test_replace_invalidates_only_the_same_purpose(repo: EmailCodeRepositoryImpl) -> None:
    user = make_user(username="ana")
    repo.replace_codes([_code(user, RECOVERY), _code(user, CONFIRMATION)])

    repo.replace_codes([_code(user, RECOVERY)])

    assert EmailCode.objects.filter(purpose=RECOVERY).count() == 1
    assert EmailCode.objects.filter(purpose=CONFIRMATION).count() == 1


def test_one_code_per_account_and_purpose_is_enforced() -> None:
    user = make_user(username="ana")
    fields = {"user": user, "purpose": RECOVERY, "address": ADDRESS, "expires_at": NOW}
    EmailCode.objects.create(code_digest="a", **fields)

    with pytest.raises(IntegrityError), transaction.atomic():
        EmailCode.objects.create(code_digest="b", **fields)


def test_lock_live_ignores_expired_codes(repo: EmailCodeRepositoryImpl) -> None:
    live, expired = make_user(username="ana"), make_user(username="joao")
    repo.replace_codes([_code(live), _code(expired, expires_at=NOW - timedelta(seconds=1))])

    pending = repo.lock_live_for_address(RECOVERY, ADDRESS, NOW)

    assert [code.user_id for code in pending] == [live.pk]


def test_lock_live_for_user_is_scoped_to_the_purpose(repo: EmailCodeRepositoryImpl) -> None:
    user = make_user(username="ana")
    repo.replace_codes([_code(user, RECOVERY)])

    assert repo.lock_live_for_user(CONFIRMATION, user.pk, NOW) == []
    assert len(repo.lock_live_for_user(RECOVERY, user.pk, NOW)) == 1


def test_failure_counts_on_every_code_of_the_address(repo: EmailCodeRepositoryImpl) -> None:
    ana, joao = make_user(username="ana"), make_user(username="joao")
    other = make_user(username="other")
    repo.replace_codes([_code(ana), _code(joao), _code(other, address="other@example.com")])

    repo.count_failure_for_address(RECOVERY, ADDRESS)

    counts = dict(EmailCode.objects.values_list("address", "failed_attempts"))
    assert counts == {ADDRESS: 1, "other@example.com": 0}


def test_the_limit_deletes_every_code_of_the_address(repo: EmailCodeRepositoryImpl) -> None:
    repo.replace_codes([_code(make_user(username="ana")), _code(make_user(username="joao"))])

    for _ in range(5):
        repo.count_failure_for_address(RECOVERY, ADDRESS)

    assert not EmailCode.objects.exists()


def test_failure_for_a_user_does_not_touch_others(repo: EmailCodeRepositoryImpl) -> None:
    ana, joao = make_user(username="ana"), make_user(username="joao")
    repo.replace_codes([_code(ana, CONFIRMATION), _code(joao, CONFIRMATION)])

    repo.count_failure_for_user(CONFIRMATION, ana.pk)

    assert EmailCode.objects.get(user=ana).failed_attempts == 1
    assert EmailCode.objects.get(user=joao).failed_attempts == 0


def test_consume_deletes_only_that_account_and_purpose(repo: EmailCodeRepositoryImpl) -> None:
    ana, joao = make_user(username="ana"), make_user(username="joao")
    repo.replace_codes([_code(ana, RECOVERY), _code(ana, CONFIRMATION), _code(joao, RECOVERY)])

    repo.consume(RECOVERY, ana.pk)

    assert EmailCode.objects.count() == 2
    assert not EmailCode.objects.filter(user=ana, purpose=RECOVERY).exists()


def test_delete_for_user_covers_both_purposes(repo: EmailCodeRepositoryImpl) -> None:
    ana, joao = make_user(username="ana"), make_user(username="joao")
    repo.replace_codes([_code(ana, RECOVERY), _code(ana, CONFIRMATION), _code(joao, RECOVERY)])

    repo.delete_for_user(ana.pk)

    assert list(EmailCode.objects.values_list("user_id", flat=True)) == [joao.pk]


def test_purge_removes_expired_codes_and_stale_ledgers(repo: EmailCodeRepositoryImpl) -> None:
    now = timezone.now()
    live, expired = make_user(username="ana"), make_user(username="joao")
    repo.replace_codes(
        [
            _code(live, expires_at=now + timedelta(minutes=5)),
            _code(expired, expires_at=now - timedelta(minutes=5)),
        ]
    )
    EmailSendLedger.objects.create(address_key="fresh")
    EmailSendLedger.objects.create(address_key="stale")
    EmailSendLedger.objects.filter(address_key="stale").update(
        updated_at=now - timedelta(hours=1, seconds=1)
    )

    assert repo.purge_expired(now) == 2

    assert EmailCode.objects.get().user_id == live.pk
    assert EmailSendLedger.objects.get().address_key == "fresh"


def test_purge_command_runs_through_the_container(repo: EmailCodeRepositoryImpl) -> None:
    repo.replace_codes(
        [_code(make_user(username="ana"), expires_at=timezone.now() - timedelta(minutes=1))]
    )
    output = StringIO()

    call_command("purge_expired_email_codes", stdout=output)

    assert "purged 1" in output.getvalue()
    assert not EmailCode.objects.exists()


def test_recovery_accounts_needs_active_account_with_a_password() -> None:
    repo = UserRepositoryImpl()
    eligible = make_user(username="ana")
    google_only = make_user(username="google")
    google_only.set_unusable_password()
    google_only.save()
    inactive = make_user(username="inactive", is_active=False)  # type: ignore[arg-type]
    other = make_user(username="other")
    for user, address in [
        (eligible, ADDRESS),
        (google_only, ADDRESS),
        (inactive, ADDRESS),
        (other, "other@example.com"),
    ]:
        user.profile.recovery_email = address
        user.profile.save()

    assert repo.recovery_accounts(ADDRESS) == [eligible]
    assert repo.get_recovery_account(eligible.pk, ADDRESS) == eligible
    assert repo.get_recovery_account(google_only.pk, ADDRESS) is None
    assert repo.get_recovery_account(inactive.pk, ADDRESS) is None
    assert repo.get_recovery_account(other.pk, ADDRESS) is None


def test_recovery_accounts_does_not_read_user_email() -> None:
    make_user(username="google", email=ADDRESS)

    assert UserRepositoryImpl().recovery_accounts(ADDRESS) == []


def test_lockout_resetter_normalises_the_username() -> None:
    AccessAttempt.objects.create(
        username="ana.paula", ip_address="203.0.113.1", user_agent="", failures_since_start=5
    )
    AccessAttempt.objects.create(
        username="other", ip_address="203.0.113.1", user_agent="", failures_since_start=5
    )

    AxesLockoutResetter().reset(" Ana.Paula ")

    assert list(AccessAttempt.objects.values_list("username", flat=True)) == ["other"]
    AccessAttempt.objects.all().delete()
