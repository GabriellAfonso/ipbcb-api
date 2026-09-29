from unittest.mock import MagicMock

from core.domain.exceptions import (
    AlbumRestoreNameConflictError,
    DomainError,
    MediaFileNotFoundError,
    MediaFileTrashedError,
    TrashedParentError,
    TrashEntryNotFoundError,
)
from core.http.exceptions import custom_exception_handler


def _handle(exc: DomainError) -> tuple[int, dict[str, object]]:
    response = custom_exception_handler(exc, {"request": MagicMock(), "view": MagicMock()})
    assert response is not None
    return response.status_code, dict(response.data)


class TestTrashEntryNotFound:
    def test_404_with_kind_and_id(self) -> None:
        status, body = _handle(TrashEntryNotFoundError("album", 9))

        assert status == 404
        assert body["error_code"] == "NOT_FOUND"
        assert "album 9" in str(body["detail"])
        assert (body["kind"], body["id"]) == ("album", 9)


class TestTrashedParent:
    def test_400_names_item_and_parent(self) -> None:
        status, body = _handle(TrashedParentError("photo", 301, 7))

        assert status == 400
        assert body["error_code"] == "VALIDATION_ERROR"
        assert "foto 301" in str(body["detail"])
        assert "álbum 7" in str(body["detail"])
        assert (body["kind"], body["id"], body["trashed_parent_id"]) == ("photo", 301, 7)

    def test_album_wording(self) -> None:
        assert "o álbum 9" in str(TrashedParentError("album", 9, 7))


class TestAlbumRestoreNameConflict:
    def test_400_names_album_name_and_sibling(self) -> None:
        status, body = _handle(AlbumRestoreNameConflictError(7, "Culto", 12))

        assert status == 400
        assert body["error_code"] == "VALIDATION_ERROR"
        detail = str(body["detail"])
        assert "7" in detail and "Culto" in detail and "12" in detail
        assert (body["album_id"], body["name"], body["conflicting_album_id"]) == (7, "Culto", 12)


class TestMediaFileTrashed:
    def test_is_a_missing_file_to_the_caller(self) -> None:
        exc = MediaFileTrashedError("gallery/7/x.jpg")

        assert isinstance(exc, MediaFileNotFoundError)
        assert str(exc) == str(MediaFileNotFoundError("gallery/7/x.jpg"))
        assert _handle(exc)[0] == 404
