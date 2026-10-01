from django.urls import path

from features.songs.views.hymnal import HymnalAPI
from features.songs.views.hymnal_history import (
    HymnalHistoryIngestAPI,
    HymnalHistoryOccurrencesAPI,
    HymnalHistorySettingsAPI,
    HymnalHistoryTopHymnsAPI,
    ServiceWindowDetailAPI,
    ServiceWindowListCreateAPI,
)
from features.songs.views.register_plays import RegisterSundayPlaysAPI
from features.songs.views.setlists import (
    CurrentSetlistAPI,
    PendingConfirmationSetlistsAPI,
    SetlistByDateAPI,
)
from features.songs.views.songs import (
    AllSongsAPI,
    ChordChartDetailAPI,
    ChordChartListAPI,
    LyricsDetailAPI,
    LyricsListAPI,
    SongsBySundayAPI,
    SuggestedSongsAPI,
    TopSongsAPI,
    TopTonesAPI,
)

urlpatterns = [
    path("api/songs/", AllSongsAPI.as_view(), name="all_songs"),
    path("api/songs-by-sunday/", SongsBySundayAPI.as_view(), name="songs_by_sunday"),
    path("api/top-songs/", TopSongsAPI.as_view(), name="top_songs"),
    path("api/top-tones/", TopTonesAPI.as_view(), name="top_tones"),
    path("api/suggested-songs/", SuggestedSongsAPI.as_view(), name="suggested_songs"),
    path("api/hymnal/", HymnalAPI.as_view(), name="hymnal"),
    path("api/played/register/", RegisterSundayPlaysAPI.as_view(), name="register_sunday_plays"),
    # current/ and pending-confirmation/ before <day>/, which would otherwise swallow them.
    path("api/setlists/current/", CurrentSetlistAPI.as_view(), name="setlist_current"),
    path(
        "api/setlists/pending-confirmation/",
        PendingConfirmationSetlistsAPI.as_view(),
        name="setlist_pending_confirmation",
    ),
    path("api/setlists/<str:day>/", SetlistByDateAPI.as_view(), name="setlist_by_date"),
    path("api/chord-charts/", ChordChartListAPI.as_view(), name="chord_charts"),
    path("api/chord-charts/<int:pk>/", ChordChartDetailAPI.as_view(), name="chord_chart_detail"),
    path("api/lyrics/", LyricsListAPI.as_view(), name="lyrics"),
    path("api/lyrics/<int:pk>/", LyricsDetailAPI.as_view(), name="lyrics_detail"),
    path(
        "api/hymnal-history/events/",
        HymnalHistoryIngestAPI.as_view(),
        name="hymnal_history_events",
    ),
    path(
        "api/hymnal-history/occurrences/",
        HymnalHistoryOccurrencesAPI.as_view(),
        name="hymnal_history_occurrences",
    ),
    path(
        "api/hymnal-history/top-hymns/",
        HymnalHistoryTopHymnsAPI.as_view(),
        name="hymnal_history_top_hymns",
    ),
    path(
        "api/hymnal-history/settings/",
        HymnalHistorySettingsAPI.as_view(),
        name="hymnal_history_settings",
    ),
    path(
        "api/hymnal-history/service-windows/",
        ServiceWindowListCreateAPI.as_view(),
        name="service_windows",
    ),
    path(
        "api/hymnal-history/service-windows/<int:pk>/",
        ServiceWindowDetailAPI.as_view(),
        name="service_window_detail",
    ),
]
