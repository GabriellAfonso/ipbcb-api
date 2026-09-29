import pytest

from core.domain.exceptions import ValidationError
from features.gallery.domain.gallery_rules import (
    compare_order_ids,
    fit_photo_name,
    normalize_album_name,
)


class TestNormalizeAlbumName:
    def test_trims_whitespace(self) -> None:
        assert normalize_album_name("  Retiro 2026 \n") == "Retiro 2026"

    def test_keeps_case(self) -> None:
        assert normalize_album_name("retiros") == "retiros"

    @pytest.mark.parametrize("raw", ["", "   ", "\t"])
    def test_blank_is_refused(self, raw: str) -> None:
        with pytest.raises(ValidationError, match="vazio"):
            normalize_album_name(raw)


class TestFitPhotoName:
    def test_short_name_unchanged(self) -> None:
        assert fit_photo_name("IMG_0042.jpg") == "IMG_0042.jpg"

    def test_long_name_keeps_extension(self) -> None:
        name = fit_photo_name("a" * 150 + ".jpeg")

        assert len(name) == 100
        assert name.endswith(".jpeg")

    def test_long_name_without_extension_is_cut(self) -> None:
        assert fit_photo_name("b" * 150) == "b" * 100

    def test_exactly_at_limit_unchanged(self) -> None:
        name = "c" * 96 + ".png"
        assert fit_photo_name(name) == name


class TestCompareOrderIds:
    def test_exact_order(self) -> None:
        assert compare_order_ids([3, 1, 2], {1, 2, 3}).is_exact

    def test_empty_against_empty_is_exact(self) -> None:
        assert compare_order_ids([], set()).is_exact

    def test_missing(self) -> None:
        diff = compare_order_ids([1], {1, 2})
        assert (diff.missing, diff.is_exact) == ([2], False)

    def test_unexpected(self) -> None:
        assert compare_order_ids([1, 2, 9], {1, 2}).unexpected == [9]

    def test_repeated(self) -> None:
        assert compare_order_ids([1, 2, 1], {1, 2}).repeated == [1]
