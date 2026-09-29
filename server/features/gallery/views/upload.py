from collections.abc import Mapping, Sequence

from dependency_injector.wiring import Provide, inject
from django.core.files.uploadedfile import UploadedFile
from django.http import HttpRequest, HttpResponse
from django.middleware.csrf import get_token
from django.shortcuts import redirect
from django.utils.html import escape

from config.di import Container
from core.domain.exceptions import AlbumNotFoundError, NoPhotoAcceptedError
from features.gallery.dtos.gallery_dtos import AlbumView
from features.gallery.services.album_service import AlbumService
from features.gallery.services.gallery_service import GalleryService


def album_labels(albums: Sequence[AlbumView]) -> list[tuple[int, str]]:
    """(id, "Parent / Child") for each album, in the given order. Names repeat across parents,
    so the dropdown shows the path.

    >>> album_labels([root_view, child_view])
    [(1, 'Retiros'), (2, 'Retiros / 2026')]
    """
    by_id = {album.id: album for album in albums}
    return [(album.id, _album_path(album, by_id)) for album in albums]


def _album_path(album: AlbumView, by_id: Mapping[int, AlbumView]) -> str:
    """Names from the root down; stops at a repeated album, so a stored cycle cannot hang."""
    names: list[str] = []
    seen: set[int] = set()
    current: AlbumView | None = album
    while current is not None and current.id not in seen:
        seen.add(current.id)
        names.append(current.name)
        current = by_id.get(current.parent_id) if current.parent_id is not None else None
    return " / ".join(reversed(names))


def _build_upload_html(
    request: HttpRequest,
    albums: Sequence[tuple[int, str]],
    errors: list[str] | None = None,
) -> str:
    csrf_token = get_token(request)
    options = "".join(
        f'<option value="{album_id}">{escape(label)}</option>' for album_id, label in albums
    )
    errors_html = "".join(f'<p style="color:red">{escape(e)}</p>' for e in (errors or []))
    return f"""
    <html>
    <body>
        {errors_html}
        <form method="post" enctype="multipart/form-data">
            <input type="hidden" name="csrfmiddlewaretoken" value="{csrf_token}">
            <select name="album">{options}</select>
            <input type="file" name="images" multiple accept="image/*">
            <button type="submit">Upload</button>
        </form>
    </body>
    </html>
    """


@inject
def upload_photos(
    request: HttpRequest,
    gallery_service: GalleryService = Provide[Container.gallery_service],
    album_service: AlbumService = Provide[Container.album_service],
) -> HttpResponse:
    """Django admin upload page. Goes through the same service as ``POST /api/photos/``, so
    storage path, thumbnail, position, cover and uploader match an app upload."""
    albums = album_labels(album_service.list_albums())

    if request.method != "POST":
        return HttpResponse(_build_upload_html(request, albums))

    album_id = request.POST.get("album")
    files = request.FILES.getlist("images")
    if not album_id or not files:
        return HttpResponse(
            _build_upload_html(request, albums, ["Selecione um álbum e ao menos uma imagem."])
        )

    errors = _upload_errors(gallery_service, album_id, files, request)
    if errors:
        return HttpResponse(_build_upload_html(request, albums, errors))
    return redirect("admin:gallery_album_changelist")


def _upload_errors(
    gallery_service: GalleryService,
    album_id: str,
    files: list[UploadedFile],
    request: HttpRequest,
) -> list[str]:
    """One message per rejected file; empty when every file was stored."""
    try:
        result = gallery_service.upload_photos(int(album_id), files, request.user.pk)
    except (AlbumNotFoundError, ValueError):
        # A non-numeric album id can only come from a hand-made POST, not from the
        # select box — same answer as an album that does not exist.
        return ["Álbum não encontrado."]
    except NoPhotoAcceptedError as exc:
        return [f"{item['filename']}: {item['reason']}" for item in exc.rejected]
    return [f"{item.filename}: {item.reason}" for item in result.rejected]
