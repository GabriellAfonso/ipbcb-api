from uuid import uuid4

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

EVENTS_FOLDER = "events"


class DefaultStorageEventImageStorage:
    """Event images on Django's default storage, as ``events/{uuid}.jpg``.

    Readable through the media access check: anyone for a public event, members for a members
    event (specs/020-church-events FR-019). A replaced image gets a new name, so a URL never
    changes content and a cached copy stays right for as long as the URL is served.
    """

    def save(self, content: bytes) -> str:
        """>>> storage.save(jpeg_bytes)
        'events/8c41....jpg'
        """
        return str(default_storage.save(f"{EVENTS_FOLDER}/{uuid4().hex}.jpg", ContentFile(content)))

    def delete(self, name: str) -> None:
        """>>> storage.delete("events/8c41....jpg")"""
        default_storage.delete(name)

    def url(self, name: str) -> str:
        """>>> storage.url("events/8c41....jpg")
        '/ipbcb/media/events/8c41....jpg'
        """
        return str(default_storage.url(name))
