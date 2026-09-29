"""Small typing helpers shared by the gallery tests."""

from collections.abc import Callable
from contextlib import AbstractContextManager

from django.db.models.fields.files import FieldFile

# Type of pytest-django's ``django_capture_on_commit_callbacks`` fixture.
CaptureOnCommit = Callable[..., AbstractContextManager[list[Callable[[], object]]]]


def stored_name(field: FieldFile) -> str:
    """The storage name of a file field; empty when no file is set."""
    return field.name or ""
