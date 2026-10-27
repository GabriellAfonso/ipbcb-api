"""Reads the video shape of ``POST /api/photos/`` off the request (specs/023-gallery-videos
FR-009, FR-010, research R-04). Shape only: the video's size and format, the poster and the
client upload id's own shape are the service's to check.

Messages are in English, like the other contract errors of these views: they address whoever
builds a client, not the uploader.
"""

from collections.abc import Sequence
from typing import IO, Any

from rest_framework.request import Request

from core.domain.exceptions import ValidationError
from core.http.parsing import optional_single_value
from features.gallery.dtos.gallery_dtos import VideoUploadMeta
from features.gallery.serializers.serializers import VideoUploadSerializer

VIDEO_FIELD = "video"
_FILE_FIELDS = (VIDEO_FIELD, "poster")
_VALUE_FIELDS = ("duration_ms", "client_upload_id", "date_taken")


def is_video_upload(request: Request) -> bool:
    """True when the request carries a ``video`` file; refuses one that also carries ``image``.

    >>> is_video_upload(request)  # multipart with video=..., poster=...
    True
    """
    if not request.FILES.getlist(VIDEO_FIELD):
        return False
    if request.FILES.getlist("image"):
        raise ValidationError(
            "Send photos in 'image' or one video in 'video', not both in one request."
        )
    return True


def read_video_upload(request: Request) -> tuple[IO[bytes], IO[bytes], VideoUploadMeta]:
    """The video, its poster and what the phone read from it, each field sent exactly once.

    >>> video, poster, meta = read_video_upload(request)
    >>> meta.duration_ms
    45000
    """
    for field in _FILE_FIELDS:
        _require_one_file(request.FILES.getlist(field), field)
    for field in _VALUE_FIELDS:
        optional_single_value(request.POST.getlist(field), field)
    serializer = VideoUploadSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    fields: dict[str, Any] = serializer.validated_data
    meta = VideoUploadMeta(
        duration_ms=fields["duration_ms"],
        date_taken=fields.get("date_taken"),
        client_upload_id=fields["client_upload_id"],
    )
    return fields["video"], fields["poster"], meta


def _require_one_file(files: Sequence[Any], field: str) -> None:
    if len(files) != 1:
        raise ValidationError(f"Field '{field}' must carry exactly one file, got {len(files)}.")
