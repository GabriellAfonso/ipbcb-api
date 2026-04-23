from django.urls import path

from apps.gallery.views.gallery import AlbumPhotoListAPIView, PhotoListAPIView

urlpatterns = [
    path("api/photos/", PhotoListAPIView.as_view()),
    path("api/albums/<int:album_id>/photos/", AlbumPhotoListAPIView.as_view()),
]
