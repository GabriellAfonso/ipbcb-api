from typing import Any

from django.contrib import admin
from django.urls import path

from features.gallery.models.gallery import Album, Photo
from features.gallery.views.upload import upload_photos


@admin.register(Album)
class AlbumAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    def get_urls(self) -> list[Any]:
        urls = super().get_urls()
        custom = [
            path("upload/", self.admin_site.admin_view(upload_photos), name="gallery_upload"),
        ]
        return custom + urls


admin.site.register(Photo)
