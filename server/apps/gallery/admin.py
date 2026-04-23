from django.contrib import admin
from django.urls import path

from apps.gallery.models.gallery import Album, Photo
from apps.gallery.views.upload import upload_photos


@admin.register(Album)
class AlbumAdmin(admin.ModelAdmin):
    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path("upload/", self.admin_site.admin_view(upload_photos), name="gallery_upload"),
        ]
        return custom + urls


admin.site.register(Photo)
