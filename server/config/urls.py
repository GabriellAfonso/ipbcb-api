from django.conf import settings
from django.contrib import admin
from django.conf.urls.static import static
from django.urls import path, include
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView

from core.http.health import health_check

urlpatterns = [
    path("", include("django_prometheus.urls")),
    path("health/", health_check, name="health-check"),
    path("admin/", admin.site.urls),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/schema/swagger-ui/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    path("api/schema/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
    path("", include("features.accounts.urls")),
    path("", include("features.songs.urls")),
    path("", include("features.schedule.urls")),
    path("", include("features.members.urls")),
    path("", include("features.gallery.urls")),
    path("", include("features.bible.urls")),
    path("", include("features.media.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    # No static(MEDIA_URL) here, even in dev: media goes through the access check in
    # features.media in every mode (specs/009-protected-media-access).
