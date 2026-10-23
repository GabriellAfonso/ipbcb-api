from django.urls import path
from rest_framework_simplejwt.views import TokenBlacklistView

from features.accounts.views.access_requests import MeAccessRequestAPIView
from features.accounts.views.admin_profiles import (
    AdminAccessRequestApproveAPIView,
    AdminAccessRequestDenyAPIView,
    AdminProfileDetailAPIView,
    AdminProfileGrantAccessAPIView,
    AdminProfileListAPIView,
    AdminProfileRevokeAccessAPIView,
)
from features.accounts.views.account import AccountDeletionAPIView, PasswordChangeAPIView
from features.accounts.views.account_deletion_page import AccountDeletionPageView
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
    path("api/me/password/", PasswordChangeAPIView.as_view(), name="password_change"),
    path("api/me/delete/", AccountDeletionAPIView.as_view(), name="account_delete"),
    # Member access and access requests (specs/022-access-requests).
    path("api/me/access-requests/", MeAccessRequestAPIView.as_view(), name="me_access_requests"),
    path("api/admin/profiles/", AdminProfileListAPIView.as_view(), name="admin_profiles_list"),
    path(
        "api/admin/profiles/requests/<int:request_id>/approve/",
        AdminAccessRequestApproveAPIView.as_view(),
        name="admin_access_request_approve",
    ),
    path(
        "api/admin/profiles/requests/<int:request_id>/deny/",
        AdminAccessRequestDenyAPIView.as_view(),
        name="admin_access_request_deny",
    ),
    path(
        "api/admin/profiles/<uuid:user_id>/",
        AdminProfileDetailAPIView.as_view(),
        name="admin_profiles_detail",
    ),
    path(
        "api/admin/profiles/<uuid:user_id>/grant-access/",
        AdminProfileGrantAccessAPIView.as_view(),
        name="admin_profiles_grant_access",
    ),
    path(
        "api/admin/profiles/<uuid:user_id>/revoke-access/",
        AdminProfileRevokeAccessAPIView.as_view(),
        name="admin_profiles_revoke_access",
    ),
    # Public web page for the Play Store's "delete account" link (specs/021-user-account).
    path("conta/excluir/", AccountDeletionPageView.as_view(), name="account_deletion_page"),
]
