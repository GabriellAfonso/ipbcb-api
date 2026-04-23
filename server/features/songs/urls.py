from django.urls import path

from features.songs.views.hymnal import hymnalAPI

from features.songs.views.register_plays import RegisterSundayPlaysAPI
from features.songs.views.songs import (
    AllSongsAPI,
    SongsBySundayAPI,
    SuggestedSongsAPI,
    TopSongsAPI,
    TopTonesAPI,
    ChordChartListView,
    LyricsListView,
)

urlpatterns = [
    path("api/songs/", AllSongsAPI.as_view(), name="all_songs"),
    path("api/songs-by-sunday/", SongsBySundayAPI.as_view(), name="songs_by_sunday"),
    path("api/top-songs/", TopSongsAPI.as_view(), name="top_songs"),
    path("api/top-tones/", TopTonesAPI.as_view(), name="top_tones"),
    path("api/suggested-songs/", SuggestedSongsAPI.as_view(), name="suggested_songs"),
    path("api/hymnal/", hymnalAPI.as_view(), name="hymnal"),
    path("api/played/register/", RegisterSundayPlaysAPI.as_view(), name="register_sunday_plays"),
    path("api/chord-charts/", ChordChartListView.as_view(), name="chord_charts"),
    path("api/lyrics/", LyricsListView.as_view(), name="lyrics"),
]
