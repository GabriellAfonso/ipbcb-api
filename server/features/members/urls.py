from django.urls import path

from features.members.views.admin_member_history import AdminMemberHistoryAPIView
from features.members.views.admin_member_photo import AdminMemberPhotoAPIView
from features.members.views.admin_members import (
    AdminMemberDetailAPIView,
    AdminMemberListAPIView,
    AdminMemberOptionsAPIView,
)
from features.members.views.birthdays import MemberBirthdaysAPIView
from features.members.views.members import MemberListAPIView
from features.members.views.own_member import OwnMemberAPIView

urlpatterns = [
    path("api/members/", MemberListAPIView.as_view(), name="members_list"),
    path("api/members/birthdays/", MemberBirthdaysAPIView.as_view(), name="members_birthdays"),
    # The caller's own roll record (specs/022-access-requests); never in api/me/profile/.
    path("api/me/member/", OwnMemberAPIView.as_view(), name="me_member"),
    # Leader-only. "/admin/" because api/members/ already serves regular members.
    path("api/admin/members/", AdminMemberListAPIView.as_view(), name="admin_members_list"),
    path(
        "api/admin/members/options/",
        AdminMemberOptionsAPIView.as_view(),
        name="admin_members_options",
    ),
    path(
        "api/admin/members/<int:member_id>/",
        AdminMemberDetailAPIView.as_view(),
        name="admin_members_detail",
    ),
    path(
        "api/admin/members/<int:member_id>/photo/",
        AdminMemberPhotoAPIView.as_view(),
        name="admin_members_photo",
    ),
    path(
        "api/admin/members/<int:member_id>/history/",
        AdminMemberHistoryAPIView.as_view(),
        name="admin_members_history",
    ),
]
