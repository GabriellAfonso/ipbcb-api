from datetime import UTC, datetime, timedelta

import pytest

from features.gallery.domain.feed_cursor import (
    decode_cursor,
    encode_cursor,
    feed_window_start,
    requires_full_sync,
)

NOW = datetime(2026, 9, 29, 12, 0, 0, 123456, tzinfo=UTC)


class TestRoundTrip:
    def test_keeps_microseconds(self) -> None:
        assert decode_cursor(encode_cursor(NOW)) == NOW

    def test_is_versioned_and_unpadded(self) -> None:
        cursor = encode_cursor(NOW)
        assert cursor.startswith("v1.")
        assert "=" not in cursor


class TestDecodeRejects:
    @pytest.mark.parametrize(
        "raw",
        ["", "garbage", "v2." + encode_cursor(NOW)[3:], "v1.!!!!", "v1.AAAAAAAAAA", "v1.ãã"],
    )
    def test_anything_not_issued_is_none(self, raw: str) -> None:
        assert decode_cursor(raw) is None

    def test_seven_byte_payload_is_none(self) -> None:
        assert decode_cursor("v1.AAAAAAAAAA") is None


class TestWindow:
    def test_starts_ninety_seconds_earlier(self) -> None:
        assert feed_window_start(NOW) == NOW - timedelta(seconds=90)


class TestFullSync:
    def test_unreadable_cursor(self) -> None:
        assert requires_full_sync(None, NOW)

    def test_recent_cursor_is_a_delta(self) -> None:
        assert not requires_full_sync(NOW - timedelta(hours=1), NOW)

    def test_just_inside_mark_retention(self) -> None:
        assert not requires_full_sync(NOW - timedelta(days=90) + timedelta(seconds=91), NOW)

    def test_ninety_days_old(self) -> None:
        assert requires_full_sync(NOW - timedelta(days=90), NOW)

    def test_future_beyond_overlap(self) -> None:
        assert requires_full_sync(NOW + timedelta(seconds=91), NOW)

    def test_small_clock_skew_is_accepted(self) -> None:
        assert not requires_full_sync(NOW + timedelta(seconds=30), NOW)
