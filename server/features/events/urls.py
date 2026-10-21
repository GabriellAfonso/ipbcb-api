from django.urls import path

from features.events.views.admin_events import AdminEventDetailAPIView, AdminEventListAPIView
from features.events.views.public_events import PublicEventDetailAPIView, PublicEventListAPIView

urlpatterns = [
    path("api/events/", PublicEventListAPIView.as_view(), name="events-list"),
    path("api/events/<int:event_id>/", PublicEventDetailAPIView.as_view(), name="events-detail"),
    path("api/admin/events/", AdminEventListAPIView.as_view(), name="admin-events-list"),
    path(
        "api/admin/events/<int:event_id>/",
        AdminEventDetailAPIView.as_view(),
        name="admin-events-detail",
    ),
]
