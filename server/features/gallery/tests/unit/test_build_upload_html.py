from __future__ import annotations

from collections.abc import Generator
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from features.gallery.dtos.gallery_dtos import AlbumView
from features.gallery.views.upload import _build_upload_html, album_labels


def _album(album_id: int, name: str, parent_id: int | None = None) -> AlbumView:
    return AlbumView(
        id=album_id,
        name=name,
        parent_id=parent_id,
        description="",
        event_date=None,
        cover_path=None,
        cover_source_album_id=None,
        position=0,
        updated_at=datetime(2026, 9, 29, tzinfo=timezone.utc),
    )


class TestBuildUploadHtml:
    @pytest.fixture(autouse=True)
    def _mock_csrf(self) -> Generator[None]:
        with patch("features.gallery.views.upload.get_token", return_value="fake-csrf-token"):
            yield

    def test_contains_form_tag(self) -> None:
        html = _build_upload_html(MagicMock(), [])
        assert "<form" in html
        assert 'method="post"' in html
        assert 'enctype="multipart/form-data"' in html

    def test_contains_csrf_token(self) -> None:
        assert "fake-csrf-token" in _build_upload_html(MagicMock(), [])

    def test_renders_album_options(self) -> None:
        html = _build_upload_html(MagicMock(), [(1, "Fotos 2026"), (2, "Eventos")])
        assert '<option value="1">Fotos 2026</option>' in html
        assert '<option value="2">Eventos</option>' in html

    def test_escapes_album_labels(self) -> None:
        html = _build_upload_html(MagicMock(), [(1, "<script>")])
        assert "<script>" not in html
        assert "&lt;script&gt;" in html

    def test_no_options_when_no_albums(self) -> None:
        assert "<option" not in _build_upload_html(MagicMock(), [])

    def test_renders_errors(self) -> None:
        html = _build_upload_html(MagicMock(), [], errors=["Arquivo grande", "Formato ruim"])
        assert "Arquivo grande" in html
        assert "Formato ruim" in html
        assert "color:red" in html

    @pytest.mark.parametrize("errors", [None, []])
    def test_no_errors(self, errors: list[str] | None) -> None:
        assert "color:red" not in _build_upload_html(MagicMock(), [], errors=errors)

    def test_contains_file_input(self) -> None:
        html = _build_upload_html(MagicMock(), [])
        assert 'type="file"' in html
        assert 'name="images"' in html
        assert "multiple" in html

    def test_contains_submit_button(self) -> None:
        html = _build_upload_html(MagicMock(), [])
        assert "Upload" in html
        assert "<button" in html


class TestAlbumLabels:
    def test_shows_the_path_so_repeated_names_are_told_apart(self) -> None:
        albums = [
            _album(1, "Retiros"),
            _album(2, "2025", parent_id=1),
            _album(3, "Acampamentos"),
            _album(4, "2025", parent_id=3),
        ]

        assert album_labels(albums) == [
            (1, "Retiros"),
            (2, "Retiros / 2025"),
            (3, "Acampamentos"),
            (4, "Acampamentos / 2025"),
        ]

    def test_stops_on_a_cycle(self) -> None:
        albums = [_album(1, "A", parent_id=2), _album(2, "B", parent_id=1)]

        assert album_labels(albums) == [(1, "B / A"), (2, "A / B")]
