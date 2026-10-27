from django.urls import path

from features.bible.views import BibleDetailView, BibleListView
from features.bible.views.progress import BibleProgressSyncView, BibleProgressView
from features.bible.views.videos import (
    BibleVideoDetailView,
    BibleVideoListView,
    BibleVideoOrderView,
    BibleVideoPlacesView,
)

app_name = "bible"

# Videos and progress come before ``<str:name>``, which would otherwise read "videos" and
# "progress" as translation names (specs/025-bible-videos R-10).
urlpatterns = [
    path("api/bible/videos/", BibleVideoListView.as_view(), name="bible-videos"),
    path("api/bible/videos/order/", BibleVideoOrderView.as_view(), name="bible-videos-order"),
    path(
        "api/bible/videos/<int:video_id>/",
        BibleVideoDetailView.as_view(),
        name="bible-video-detail",
    ),
    path(
        "api/bible/videos/<int:video_id>/places/",
        BibleVideoPlacesView.as_view(),
        name="bible-video-places",
    ),
    path("api/bible/progress/", BibleProgressView.as_view(), name="bible-progress"),
    path("api/bible/progress/sync/", BibleProgressSyncView.as_view(), name="bible-progress-sync"),
    path("api/bible/", BibleListView.as_view(), name="bible-list"),
    path("api/bible/<str:name>/", BibleDetailView.as_view(), name="bible-detail"),
]
