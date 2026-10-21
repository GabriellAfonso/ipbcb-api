from features.events.domain.event_enums import EventVisibility
from features.events.models.event import Event


class EventImageLookupImpl:
    """Implements the media check's ``EventImageLookup`` port: which audience an ``events/`` file
    has. Wired in ``config/di.py`` so the media feature never imports this one
    (specs/020-church-events research R-05).
    """

    def is_public_event_image(self, relative_path: str) -> bool | None:
        """True for a public event's image, False for a members event's, None for a file that
        is no event's image. One query on the unique ``image_path`` index.

        >>> EventImageLookupImpl().is_public_event_image("events/8c41....jpg")
        True
        """
        visibility = (
            Event.objects.filter(image_path=relative_path)
            .values_list("visibility", flat=True)
            .first()
        )
        if visibility is None:
            return None
        return visibility == EventVisibility.PUBLIC.value
