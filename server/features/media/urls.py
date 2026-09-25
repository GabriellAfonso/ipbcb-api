import re

from django.conf import settings
from django.urls import re_path

from features.media.views.media_file import MediaFileAPIView


def media_route_prefix() -> str:
    """URL prefix Django sees for media, derived from MEDIA_URL.

    In production Django strips FORCE_SCRIPT_NAME from path_info, so "/ipbcb/media/" arrives
    as "media/..."; in dev and tests there is no script name and it arrives whole. The
    serializers emit MEDIA_URL in both cases, so one hardcoded pattern would miss one of them.

    >>> media_route_prefix()  # prod: FORCE_SCRIPT_NAME="/ipbcb"
    'media/'
    >>> media_route_prefix()  # dev: FORCE_SCRIPT_NAME=None
    'ipbcb/media/'
    """
    script_name = settings.FORCE_SCRIPT_NAME or ""
    return settings.MEDIA_URL.removeprefix(script_name).lstrip("/")


# ".*", not ".+": even "/ipbcb/media/" goes through the check and gets a canonical 401/404.
urlpatterns = [
    re_path(
        rf"^{re.escape(media_route_prefix())}(?P<requested_path>.*)$",
        MediaFileAPIView.as_view(),
        name="media-file",
    ),
]
