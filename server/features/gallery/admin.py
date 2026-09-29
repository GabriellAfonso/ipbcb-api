from typing import Any

from dependency_injector.wiring import Provide, inject
from django import forms
from django.contrib import admin
from django.http import HttpRequest
from django.urls import path

from config.di import Container
from core.domain.exceptions import DomainError
from features.gallery.dtos.gallery_dtos import AlbumChanges, AlbumCreate
from features.gallery.models.gallery import Album, Photo
from features.gallery.services.album_service import AlbumService
from features.gallery.views.upload import upload_photos

_ALBUM_FIELDS = ("name", "parent", "description", "event_date")


@inject
def _album_service(service: AlbumService = Provide[Container.album_service]) -> AlbumService:
    # Module level so the container wires it (admin classes are built before wiring).
    return service


class AlbumAdminForm(forms.ModelForm):  # type: ignore[type-arg]
    """Validates through the same service as the API: no duplicate sibling name, no cycle
    (specs/013-gallery-write-api FR-005, FR-006)."""

    class Meta:
        model = Album
        fields = _ALBUM_FIELDS

    def clean(self) -> dict[str, Any]:
        cleaned = super().clean() or {}
        parent = cleaned.get("parent")
        try:
            _album_service().validate_placement(
                self.instance.pk, cleaned.get("name") or "", parent.pk if parent else None
            )
        except DomainError as exc:
            raise forms.ValidationError(str(exc)) from exc
        return cleaned


@admin.register(Album)
class AlbumAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    form = AlbumAdminForm
    fields = (*_ALBUM_FIELDS, "position", "cover_image")
    readonly_fields = ("position", "cover_image")
    list_display = ("name", "parent", "position")

    def save_model(self, request: HttpRequest, obj: Album, form: Any, change: bool) -> None:
        """Save through the service, so a new or moved album goes last among its siblings."""
        values = {key: form.cleaned_data.get(key) for key in ("name", "description", "event_date")}
        values["description"] = values["description"] or ""
        parent = form.cleaned_data.get("parent")
        values["parent_id"] = parent.pk if parent else None
        if change:
            _album_service().update(obj.pk, AlbumChanges(**values))
            return
        obj.pk = obj.id = _album_service().create(AlbumCreate(**values)).id

    def get_urls(self) -> list[Any]:
        urls = super().get_urls()
        custom = [
            path("upload/", self.admin_site.admin_view(upload_photos), name="gallery_upload"),
        ]
        return custom + urls


@admin.register(Photo)
class PhotoAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    """Photos arrive only through the upload page, so every photo has a thumbnail."""

    readonly_fields = ("image", "thumbnail", "uploaded_by", "position")
    list_display = ("name", "album", "position")

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False
