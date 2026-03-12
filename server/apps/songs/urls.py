from django.urls import path

from apps.songs.views.hymnal import hymnalAPI

from apps.songs.views.register_plays import RegisterSundayPlaysAPI
from apps.songs.views.songs import (
    AllSongsAPI,
    SongsBySundayAPI,
    SuggestedSongsAPI,
    TopSongsAPI,
    TopTonesAPI,
    ChordChartListView,
    LyricsDetailView,
)

urlpatterns = [
    path("api/songs/", AllSongsAPI.as_view(), name="all_songs"),
    path("api/songs-by-sunday/", SongsBySundayAPI.as_view(), name="songs_by_sunday"),
    path("api/top-songs/", TopSongsAPI.as_view(), name="top_songs"),
    path("api/top-tones/", TopTonesAPI.as_view(), name="top_tones"),
    path("api/suggested-songs/", SuggestedSongsAPI.as_view(), name="suggested_songs"),
    path("api/hymnal/", hymnalAPI.as_view(), name="hymnal"),
    path("api/played/register/", RegisterSundayPlaysAPI.as_view(), name="register_sunday_plays"),
    path("api/songs/<int:song_id>/chord-charts/", ChordChartListView.as_view(), name="chord_charts"),
    path("api/songs/<int:song_id>/lyrics/", LyricsDetailView.as_view(), name="lyrics"),
]
