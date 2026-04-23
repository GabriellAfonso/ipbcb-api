from django.urls import path

from features.members.views.members import MemberListAPIView

urlpatterns = [
    path("api/members/", MemberListAPIView.as_view(), name="members_list"),
]
