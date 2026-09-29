from dependency_injector.wiring import Provide, inject
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from config.di import Container
from core.http.permissions import IsMemberUser
from features.gallery.serializers.feed_serializers import ChangeFeedSerializer
from features.gallery.services.gallery_change_feed_service import GalleryChangeFeedService


class GalleryChangesAPIView(APIView):
    """``GET ?since=<cursor>``: what changed since the app's last sync. Always ``200``: a cursor
    the server cannot use answers ``full_sync_required``, never an error that would block the
    app's sync for good (specs/014-gallery-trash-sync, Edge Cases)."""

    serializer_class = ChangeFeedSerializer
    permission_classes = [IsMemberUser]

    @inject
    def get(
        self,
        request: Request,
        feed_service: GalleryChangeFeedService = Provide[Container.gallery_change_feed_service],
    ) -> Response:
        # Handed over unparsed: decoding the opaque cursor is the domain's job.
        feed = feed_service.changes(request.query_params.get("since"))
        return Response(ChangeFeedSerializer(feed, context={"request": request}).data)
