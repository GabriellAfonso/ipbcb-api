from unittest.mock import MagicMock

import pytest

from core.domain.exceptions import (
    AlbumCycleError,
    AlbumNotFoundError,
    ClientUploadIdTakenError,
    ClientUploadNeedsOneFileError,
    DomainError,
    DuplicateAlbumNameError,
    ImageProcessingError,
    ImageTooLargeError,
    InvalidClientUploadIdError,
    NoPhotoAcceptedError,
    OrderMismatchError,
    PhotoNotFoundError,
    UploadedPhotoTrashedError,
)
from core.http.exceptions import custom_exception_handler


def _handle(exc: DomainError) -> tuple[int, dict[str, object]]:
    response = custom_exception_handler(exc, {"request": MagicMock(), "view": MagicMock()})
    assert response is not None
    return response.status_code, dict(response.data)


class TestNotFound:
    @pytest.mark.parametrize(
        ("exc", "key", "value"),
        [(AlbumNotFoundError(7), "album_id", 7), (PhotoNotFoundError(12), "photo_id", 12)],
    )
    def test_maps_to_404_with_the_id(self, exc: DomainError, key: str, value: int) -> None:
        status, body = _handle(exc)

        assert status == 404
        assert body["error_code"] == "NOT_FOUND"
        assert str(value) in str(body["detail"])
        assert body[key] == value


class TestAlbumCycleError:
    def test_message_names_both_albums_and_body_carries_the_chain(self) -> None:
        status, body = _handle(AlbumCycleError(3, 9, [9, 5, 3]))

        assert status == 400
        assert body["error_code"] == "VALIDATION_ERROR"
        assert "3" in str(body["detail"]) and "9" in str(body["detail"])
        assert body["chain"] == [9, 5, 3]
        assert (body["album_id"], body["parent_id"]) == (3, 9)


class TestDuplicateAlbumNameError:
    def test_is_400_with_the_name(self) -> None:
        status, body = _handle(DuplicateAlbumNameError("Retiros", None))

        assert status == 400
        assert "Retiros" in str(body["detail"])
        assert body["parent_id"] is None


class TestOrderMismatchError:
    def test_lists_every_difference(self) -> None:
        status, body = _handle(OrderMismatchError(missing=[4], unexpected=[8], repeated=[1]))

        assert status == 400
        assert "[4]" in str(body["detail"]) and "[8]" in str(body["detail"])
        assert (body["missing"], body["unexpected"], body["repeated"]) == ([4], [8], [1])


class TestNoPhotoAcceptedError:
    def test_canonical_body_carries_rejected(self) -> None:
        rejected = [{"filename": "a.txt", "reason": "Formato inválido"}]

        status, body = _handle(NoPhotoAcceptedError(rejected))

        assert status == 400
        assert body["error_code"] == "VALIDATION_ERROR"
        assert body["detail"] == "Nenhuma imagem foi aceita."
        assert body["rejected"] == rejected


class TestImageErrors:
    def test_processing_error_names_the_file(self) -> None:
        assert "IMG_0042.jpg" in str(ImageProcessingError("IMG_0042.jpg"))

    def test_too_large_names_dimensions_and_limit(self) -> None:
        message = str(ImageTooLargeError(9000, 8000, 50_000_000))

        assert "9000x8000" in message
        assert "50 megapixels" in message

    @pytest.mark.parametrize(
        "exc", [ImageProcessingError("x.jpg"), ImageTooLargeError(1, 1, 50_000_000)]
    )
    def test_both_are_400(self, exc: DomainError) -> None:
        status, _ = _handle(exc)
        assert status == 400


UPLOAD_ID = "3f2a9c1e-7b4d-4e8a-9f10-2c6b5d7e8a90"


class TestClientUploadErrors:
    def test_invalid_id_names_problem_and_expected_shape(self) -> None:
        status, body = _handle(InvalidClientUploadIdError("a b", "got ' ' at position 1", "X"))

        assert status == 400
        assert body["error_code"] == "VALIDATION_ERROR"
        assert "client_upload_id" in str(body["detail"])
        assert "position 1" in str(body["detail"])
        assert (body["client_upload_id"], body["expected"]) == ("a b", "X")

    def test_needs_one_file_carries_the_count(self) -> None:
        status, body = _handle(ClientUploadNeedsOneFileError(3))

        assert status == 400
        assert "got 3" in str(body["detail"])
        assert body["file_count"] == 3

    def test_trashed_original_is_409_without_the_photo(self) -> None:
        status, body = _handle(UploadedPhotoTrashedError(UPLOAD_ID))

        assert status == 409
        assert body["error_code"] == "CONFLICT"
        assert "lixeira" in str(body["detail"])
        assert body["client_upload_id"] == UPLOAD_ID
        assert "photo_id" not in body

    def test_taken_id_names_the_id(self) -> None:
        assert UPLOAD_ID in str(ClientUploadIdTakenError(UPLOAD_ID))
