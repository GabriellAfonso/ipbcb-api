"""Closed vocabularies of the events domain (specs/020-church-events)."""

from enum import StrEnum

from core.domain.exceptions import EventStatusFilterError


class EventVisibility(StrEnum):
    """Who sees an event on the public endpoints. The value is the wire name."""

    PUBLIC = "public"
    MEMBERS = "members"


class EventStatusFilter(StrEnum):
    """Management list filter: events still active, already past, or both."""

    ACTIVE = "active"
    PAST = "past"
    ALL = "all"


def parse_status_filter(raw: str | None) -> EventStatusFilter:
    """The filter named by ``raw``; ``all`` when absent.

    >>> parse_status_filter("past")
    <EventStatusFilter.PAST: 'past'>
    >>> parse_status_filter(None)
    <EventStatusFilter.ALL: 'all'>
    """
    if raw is None:
        return EventStatusFilter.ALL
    try:
        return EventStatusFilter(raw)
    except ValueError:
        raise EventStatusFilterError(raw, [status.value for status in EventStatusFilter]) from None
