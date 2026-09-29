from django.urls import path

from features.gallery.views.album_cover import AlbumCoverAPIView
from features.gallery.views.albums import (
    AlbumDetailAPIView,
    AlbumListCreateAPIView,
    AlbumOrderAPIView,
)
from features.gallery.views.gallery import (
    AlbumPhotoListAPIView,
    AlbumPhotoOrderAPIView,
    PhotoDetailAPIView,
    PhotoListAPIView,
)

urlpatterns = [
    path("api/albums/", AlbumListCreateAPIView.as_view()),
    path("api/albums/order/", AlbumOrderAPIView.as_view()),
    path("api/albums/<int:album_id>/", AlbumDetailAPIView.as_view()),
    path("api/albums/<int:album_id>/cover/", AlbumCoverAPIView.as_view()),
    path("api/albums/<int:album_id>/photos/", AlbumPhotoListAPIView.as_view()),
    path("api/albums/<int:album_id>/photos/order/", AlbumPhotoOrderAPIView.as_view()),
    path("api/photos/", PhotoListAPIView.as_view()),
    path("api/photos/<int:photo_id>/", PhotoDetailAPIView.as_view()),
]
