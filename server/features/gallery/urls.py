from django.urls import path

from features.gallery.views.gallery import AlbumPhotoListAPIView, PhotoListAPIView

urlpatterns = [
    path("api/photos/", PhotoListAPIView.as_view()),
    path("api/albums/<int:album_id>/photos/", AlbumPhotoListAPIView.as_view()),
]
