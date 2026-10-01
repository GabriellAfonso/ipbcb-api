from django.urls import path
from rest_framework_simplejwt.views import TokenBlacklistView

from features.accounts.views.auth import GoogleLoginAPI, LoginAPI, RefreshAPI, RegisterAPI
from features.accounts.views.devices import (
    DeviceTokenRegisterAPIView,
    DeviceTokenUnregisterAPIView,
)
from features.accounts.views.profile import MeProfileAPIView, ProfilePhotoAPIView

urlpatterns = [
    path("api/auth/google/", GoogleLoginAPI.as_view(), name="google_login"),
    path("api/auth/register/", RegisterAPI.as_view(), name="register"),
    path("api/auth/login/", LoginAPI.as_view(), name="login"),
    path("api/auth/refresh/", RefreshAPI.as_view(), name="token_refresh"),
    # Blacklists the refresh token it is given. The access token stays valid until it
    # expires — revoking it per request would mean a database read on every call, which
    # is the cost JWT exists to avoid.
    path("api/auth/logout/", TokenBlacklistView.as_view(), name="logout"),
    path("api/me/profile/photo/", ProfilePhotoAPIView.as_view(), name="profile_photo"),
    path("api/me/profile/", MeProfileAPIView.as_view(), name="me_profile"),
    path("api/me/devices/", DeviceTokenRegisterAPIView.as_view(), name="device_register"),
    path(
        "api/me/devices/unregister/",
        DeviceTokenUnregisterAPIView.as_view(),
        name="device_unregister",
    ),
]
