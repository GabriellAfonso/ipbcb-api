"""Turning event DTOs into response bodies, shared by the public and the management views."""

from collections.abc import Sequence
from typing import Any

from rest_framework.request import Request

from features.events.dtos import EventRecordDTO
from features.events.serializers import EventPublicSerializer, EventRecordSerializer
from features.events.services.event_service import EventService


def _context(request: Request, event_service: EventService) -> dict[str, Any]:
    return {"request": request, "image_url_path": event_service.image_url_path}


def public_body(
    request: Request, event_service: EventService, record: EventRecordDTO
) -> dict[str, Any]:
    """The public resource of one event.

    >>> public_body(request, service, record)["image_url"]
    'https://host/ipbcb/media/events/8c41....jpg'
    """
    serializer = EventPublicSerializer(
        record.model_dump(), context=_context(request, event_service)
    )
    return dict(serializer.data)


def public_list_body(
    request: Request, event_service: EventService, records: Sequence[EventRecordDTO]
) -> list[Any]:
    """The public resources of several events, in the given order.

    >>> public_list_body(request, service, [record])[0]["title"]
    'Congresso de Jovens'
    """
    dumps = [record.model_dump() for record in records]
    serializer = EventPublicSerializer(dumps, many=True, context=_context(request, event_service))
    return list(serializer.data)


def record_body(
    request: Request, event_service: EventService, record: EventRecordDTO
) -> dict[str, Any]:
    """The management resource of one event (public fields plus audit fields).

    >>> record_body(request, service, record)["created_by"]
    {'id': '5b0e…', 'name': 'Ana Paula'}
    """
    serializer = EventRecordSerializer(
        record.model_dump(), context=_context(request, event_service)
    )
    return dict(serializer.data)


def record_list_body(
    request: Request, event_service: EventService, records: Sequence[EventRecordDTO]
) -> dict[str, Any]:
    """The management list body, ``{"events": [...]}``.

    >>> record_list_body(request, service, [])
    {'events': []}
    """
    dumps = [record.model_dump() for record in records]
    serializer = EventRecordSerializer(dumps, many=True, context=_context(request, event_service))
    return {"events": serializer.data}
