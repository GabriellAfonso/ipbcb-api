from dependency_injector.wiring import Provide, inject
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from urllib.parse import quote

from django.conf import settings
from django.http import FileResponse, HttpResponse, HttpResponseBase

from config.di import Container
from core.http.permissions import IsAdminUser, IsMemberUser
from features.media.dtos.media_dtos import MediaFile, MediaViewer
from features.media.services.media_access_service import MediaAccessService


class MediaFileAPIView(APIView):
    """Serves ``/ipbcb/media/<path>`` only to callers the folder's rule allows.

    Authentication is DRF's; the access decision is ``MediaAccessService``'s. This view only
    translates the caller into a ``MediaViewer`` and the decision into an HTTP response.
    """

    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "media"
    http_method_names = ["get", "head"]

    @inject
    def get(
        self,
        request: Request,
        requested_path: str,
        media_access_service: MediaAccessService = Provide[Container.media_access_service],
    ) -> HttpResponseBase:
        media_file = media_access_service.authorize(requested_path, self._viewer(request))
        return self._file_response(media_file, media_access_service)

    def _viewer(self, request: Request) -> MediaViewer:
        # The same permission classes every other endpoint uses, so the flags are read one way.
        return MediaViewer(
            is_member=IsMemberUser().has_permission(request, self),
            is_leader=IsAdminUser().has_permission(request, self),
        )

    def _file_response(
        self, media_file: MediaFile, media_access_service: MediaAccessService
    ) -> HttpResponseBase:
        # Read per request: production always has DEBUG off and nginx in front; development
        # has neither, so Django streams the file after the very same checks.
        if settings.DEBUG:
            return _direct_file_response(media_file, media_access_service)
        return _accel_redirect_response(media_file)


# private: never in a shared cache. no-cache: the phone keeps the file but revalidates on
# every use, so each view passes the access check again. Constitution, Caching exception.
_MEDIA_CACHE_CONTROL = "private, no-cache"


def _accel_redirect_response(media_file: MediaFile) -> HttpResponse:
    """Empty response telling nginx which file to stream.

    Percent-encoded because gallery names keep Unicode letters and Django would MIME-encode a
    non-Latin-1 header value; nginx unescapes the URI. Content-Type is explicit because nginx
    keeps an upstream one — Django's default text/html would otherwise label every image.

    >>> _accel_redirect_response(media_file)["X-Accel-Redirect"]
    '/ipbcb/protected-media/gallery/retiro/x.jpg'
    """
    response = HttpResponse(b"", content_type=media_file.content_type)
    location = settings.PROTECTED_MEDIA_LOCATION + media_file.relative_path
    response["X-Accel-Redirect"] = quote(location, safe="/")
    response["Cache-Control"] = _MEDIA_CACHE_CONTROL
    return response


def _direct_file_response(
    media_file: MediaFile, media_access_service: MediaAccessService
) -> FileResponse:
    """The file itself, for development without nginx. Never used in production.

    >>> _direct_file_response(media_file, service).streaming_content
    """
    response = FileResponse(
        media_access_service.open(media_file), content_type=media_file.content_type
    )
    response["Cache-Control"] = _MEDIA_CACHE_CONTROL
    return response
