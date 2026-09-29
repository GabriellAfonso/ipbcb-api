from django.urls import path

from features.gallery.views.album_cover import AlbumCoverAPIView
from features.gallery.views.albums import (
    AlbumDetailAPIView,
    AlbumListCreateAPIView,
    AlbumOrderAPIView,
)
from features.gallery.views.changes import GalleryChangesAPIView
from features.gallery.views.gallery import (
    AlbumPhotoListAPIView,
    AlbumPhotoOrderAPIView,
    PhotoDetailAPIView,
    PhotoListAPIView,
)
from features.gallery.views.tags import (
    PhotoMembersAPIView,
    PhotoTagsBulkAPIView,
    TaggableMembersAPIView,
    TaggedMembersAPIView,
)
from features.gallery.views.trash import (
    AlbumRestoreAPIView,
    PhotoRestoreAPIView,
    TrashListAPIView,
)

urlpatterns = [
    path("api/albums/", AlbumListCreateAPIView.as_view()),
    path("api/albums/order/", AlbumOrderAPIView.as_view()),
    path("api/albums/<int:album_id>/", AlbumDetailAPIView.as_view()),
    path("api/albums/<int:album_id>/cover/", AlbumCoverAPIView.as_view()),
    path("api/albums/<int:album_id>/photos/", AlbumPhotoListAPIView.as_view()),
    path("api/albums/<int:album_id>/photos/order/", AlbumPhotoOrderAPIView.as_view()),
    path("api/photos/", PhotoListAPIView.as_view()),
    path("api/photos/members/", PhotoTagsBulkAPIView.as_view()),
    path("api/photos/<int:photo_id>/", PhotoDetailAPIView.as_view()),
    path("api/photos/<int:photo_id>/members/", PhotoMembersAPIView.as_view()),
    path("api/gallery/trash/", TrashListAPIView.as_view()),
    path("api/gallery/trash/albums/<int:album_id>/restore/", AlbumRestoreAPIView.as_view()),
    path("api/gallery/trash/photos/<int:photo_id>/restore/", PhotoRestoreAPIView.as_view()),
    path("api/gallery/changes/", GalleryChangesAPIView.as_view()),
    path("api/gallery/taggable-members/", TaggableMembersAPIView.as_view()),
    path("api/gallery/tagged-members/", TaggedMembersAPIView.as_view()),
]
