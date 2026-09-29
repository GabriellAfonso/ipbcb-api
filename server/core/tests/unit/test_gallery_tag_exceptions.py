"""Tag write refusals leave the API in the canonical shape (specs/015-gallery-member-tags)."""

from unittest.mock import MagicMock

from core.domain.exceptions import (
    DomainError,
    PhotoTagReferenceError,
    TagBulkLimitError,
    TagListOverlapError,
)
from core.http.exceptions import custom_exception_handler


def _handle(exc: DomainError) -> tuple[int, dict[str, object]]:
    response = custom_exception_handler(exc, {"request": MagicMock(), "view": MagicMock()})
    assert response is not None
    return response.status_code, dict(response.data)


class TestPhotoTagReference:
    def test_404_listing_every_missing_id_sorted(self) -> None:
        status, body = _handle(PhotoTagReferenceError([302, 301], [99]))

        assert status == 404
        assert body["error_code"] == "NOT_FOUND"
        assert body["missing_photo_ids"] == [301, 302]
        assert body["missing_member_ids"] == [99]
        assert "[301, 302]" in str(body["detail"])
        assert "[99]" in str(body["detail"])


class TestTagBulkLimit:
    def test_400_with_count_and_limit(self) -> None:
        status, body = _handle(TagBulkLimitError(201, 200))

        assert status == 400
        assert body["error_code"] == "VALIDATION_ERROR"
        assert (body["photo_count"], body["limit"]) == (201, 200)
        assert "201" in str(body["detail"])


class TestTagListOverlap:
    def test_400_naming_the_members(self) -> None:
        status, body = _handle(TagListOverlapError([40, 12]))

        assert status == 400
        assert body["error_code"] == "VALIDATION_ERROR"
        assert body["member_ids"] == [12, 40]
        assert "[12, 40]" in str(body["detail"])
