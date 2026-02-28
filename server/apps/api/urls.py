from django.urls import path
from apps.api.views.gallery import PhotoListAPIView, AlbumPhotoListAPIView
from apps.api.views.gambiarra import upload_photos
from rest_framework_simplejwt.views import TokenRefreshView
from apps.api.views.auth import LoginAPI, RegisterAPI
from apps.api.views.hymnal import hymnalAPI
from apps.api.views.members import MemberListAPIView
from apps.api.views.profile import MeProfileAPIView, ProfilePhotoAPIView
from apps.api.views.register_sunday_plays import RegisterSundayPlaysAPI
from apps.api.views.schedule import (
    CurrentMonthlyScheduleAPI,
    MonthlySchedulePreviewAPI,
    MonthlyScheduleSaveAPI,
)
from apps.api.views.songs import (
    AllSongsAPI,
    SongsBySundayAPI,
    SuggestedSongsAPI,
    TopSongsAPI,
    TopTonesAPI,
)

app_name = "apps.api"

urlpatterns = [
    path("gallery/upload/", upload_photos, name="upload_photos"),

    # region 📸 Gallery
    path("api/photos/", PhotoListAPIView.as_view()),
    path("api/albums/<str:name>/photos/", AlbumPhotoListAPIView.as_view()),
    # endregion

    # region 🎵 MÚSICAS
    path("api/songs/", AllSongsAPI.as_view(), name="all_songs"),
    path("api/songs-by-sunday/", SongsBySundayAPI.as_view(), name="songs_by_sunday"),
    path("api/top-songs/", TopSongsAPI.as_view(), name="top_songs"),
    path("api/top-tones/", TopTonesAPI.as_view(), name="top_tones"),
    path("api/suggested-songs/", SuggestedSongsAPI.as_view(), name="suggested_songs"),
    # endregion

    # region 🗓️ ESCALA (novo fluxo)
    path("api/schedule/current/", CurrentMonthlyScheduleAPI.as_view(), name="schedule_current"),

    # endregion

    # region 🔑 AUTH & PROFILE
    path("api/hymnal/", hymnalAPI.as_view(), name="hymnal"),
    path("api/auth/register/", RegisterAPI.as_view(), name="register"),
    path("api/auth/login/", LoginAPI.as_view(), name="login"),
    path("api/auth/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("api/me/profile/photo/", ProfilePhotoAPIView.as_view(), name="profile_photo"),
    path("api/me/profile/", MeProfileAPIView.as_view()),
    # endregion

    # region ✅ ADMIN
    path("api/played/register/", RegisterSundayPlaysAPI.as_view(), name="register_sunday_plays"),
    path("api/members/", MemberListAPIView.as_view(), name="members_list"),

    path("api/schedule/save/", MonthlyScheduleSaveAPI.as_view(), name="schedule_save"),
    path("api/schedule/generate/", MonthlySchedulePreviewAPI.as_view(), name="generate_schedule"),

    # endregion
]