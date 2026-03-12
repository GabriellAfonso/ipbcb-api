from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from apps.accounts.views.auth import GoogleLoginAPI, LoginAPI, RegisterAPI
from apps.accounts.views.profile import MeProfileAPIView, ProfilePhotoAPIView

urlpatterns = [
    path("api/auth/google/", GoogleLoginAPI.as_view(), name="google_login"),
    path("api/auth/register/", RegisterAPI.as_view(), name="register"),
    path("api/auth/login/", LoginAPI.as_view(), name="login"),
    path("api/auth/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("api/me/profile/photo/", ProfilePhotoAPIView.as_view(), name="profile_photo"),
    path("api/me/profile/", MeProfileAPIView.as_view(), name="me_profile"),
]
