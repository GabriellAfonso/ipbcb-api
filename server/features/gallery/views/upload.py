from typing import IO

from django.db.models import QuerySet
from django.http import HttpRequest, HttpResponse
from django.middleware.csrf import get_token
from django.shortcuts import get_object_or_404, redirect
from PIL import Image

from features.gallery.models.gallery import Album, Photo

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


def _is_valid_image(f: IO[bytes]) -> bool:
    try:
        img = Image.open(f)
        img.verify()
        f.seek(0)
        return True
    except Exception:
        return False


def _build_upload_html(
    request: HttpRequest,
    albums: QuerySet[Album],
    errors: list[str] | None = None,
) -> str:
    csrf_token = get_token(request)
    options = "".join(f'<option value="{album.pk}">{album.name}</option>' for album in albums)
    errors_html = "".join(f'<p style="color:red">{e}</p>' for e in (errors or []))
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


def upload_photos(request: HttpRequest) -> HttpResponse:
    albums = Album.objects.all()

    if request.method == "POST":
        album_id = request.POST.get("album")
        files = request.FILES.getlist("images")

        if not album_id or not files:
            return HttpResponse(
                _build_upload_html(request, albums, ["Selecione um álbum e ao menos uma imagem."])
            )

        album = get_object_or_404(Album, pk=album_id)
        errors: list[str] = []

        for f in files:
            if f.size is not None and f.size > MAX_FILE_SIZE:
                errors.append(f"{f.name or f}: arquivo muito grande (máx. 10 MB).")
                continue
            if not _is_valid_image(f):
                errors.append(f"{f.name or f}: formato inválido. Use JPEG, PNG, WEBP ou GIF.")
                continue
            Photo.objects.create(album=album, image=f, name=f.name or "")

        if errors:
            return HttpResponse(_build_upload_html(request, albums, errors))

        return redirect("admin:gallery_album_changelist")

    return HttpResponse(_build_upload_html(request, albums))
