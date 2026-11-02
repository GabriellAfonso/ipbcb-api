"""The pure rules of the e-mail codes (specs/028-password-recovery)."""

import re
from datetime import UTC, datetime, timedelta

from django.test import override_settings

from features.accounts.domain.email_codes import (
    EmailCodePurpose,
    address_key,
    code_digest,
    digests_match,
    generate_codes,
    send_wait_seconds,
    sends_inside_window,
)

NOW = datetime(2026, 11, 2, 12, 0, tzinfo=UTC)
ADDRESS = "ana@example.com"


def test_generated_codes_have_six_digits() -> None:
    assert all(re.fullmatch(r"\d{6}", code) for code in generate_codes(50))


def test_generated_codes_in_one_batch_differ() -> None:
    assert len(set(generate_codes(200))) == 200


def test_digest_is_not_the_code() -> None:
    assert "123456" not in code_digest(EmailCodePurpose.RECOVERY, ADDRESS, "123456")


def test_digest_is_repeatable() -> None:
    first = code_digest(EmailCodePurpose.RECOVERY, ADDRESS, "123456")
    assert digests_match(first, code_digest(EmailCodePurpose.RECOVERY, ADDRESS, "123456"))


def test_digest_is_bound_to_the_purpose() -> None:
    recovery = code_digest(EmailCodePurpose.RECOVERY, ADDRESS, "123456")
    assert recovery != code_digest(EmailCodePurpose.CONFIRMATION, ADDRESS, "123456")


def test_digest_is_bound_to_the_address() -> None:
    recovery = code_digest(EmailCodePurpose.RECOVERY, ADDRESS, "123456")
    assert recovery != code_digest(EmailCodePurpose.RECOVERY, "other@example.com", "123456")


def test_digest_depends_on_the_secret_key() -> None:
    first = code_digest(EmailCodePurpose.RECOVERY, ADDRESS, "123456")
    with override_settings(SECRET_KEY="another-test-only-key-with-enough-bytes-for-hs256"):
        assert first != code_digest(EmailCodePurpose.RECOVERY, ADDRESS, "123456")


def test_address_key_does_not_hold_the_address() -> None:
    assert "ana" not in address_key(ADDRESS)


def test_address_key_differs_between_addresses() -> None:
    assert address_key(ADDRESS) != address_key("other@example.com")


def test_sends_outside_the_hour_stop_counting() -> None:
    inside = NOW - timedelta(minutes=59)
    assert sends_inside_window([NOW - timedelta(minutes=60), inside], NOW) == [inside]


def test_sends_inside_window_come_oldest_first() -> None:
    newer, older = NOW - timedelta(minutes=1), NOW - timedelta(minutes=2)
    assert sends_inside_window([newer, older], NOW) == [older, newer]


def test_first_send_has_no_wait() -> None:
    assert send_wait_seconds([], NOW) == 0


def test_second_send_inside_the_minute_waits_for_the_rest_of_it() -> None:
    assert send_wait_seconds([NOW - timedelta(seconds=20)], NOW) == 40


def test_send_after_the_minute_has_no_wait() -> None:
    assert send_wait_seconds([NOW - timedelta(seconds=60)], NOW) == 0


def test_sixth_send_in_the_hour_waits_for_the_oldest_to_leave() -> None:
    recent = [NOW - timedelta(minutes=minutes) for minutes in (50, 40, 30, 20, 10)]
    assert send_wait_seconds(recent, NOW) == 10 * 60


def test_four_sends_in_the_hour_do_not_block_the_fifth() -> None:
    recent = [NOW - timedelta(minutes=minutes) for minutes in (40, 30, 20, 10)]
    assert send_wait_seconds(recent, NOW) == 0


def test_the_limit_is_rolling_across_a_window_boundary() -> None:
    """A fixed window would allow this burst to continue right after its boundary."""
    recent = [NOW - timedelta(minutes=minutes) for minutes in (5, 4, 3, 2, 1)]
    assert send_wait_seconds(recent, NOW) == 55 * 60
