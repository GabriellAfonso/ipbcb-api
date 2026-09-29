"""Guards for values coming straight off the request, before they are coerced.

Views that unpack ``**request.data`` or call ``int()`` on a raw field turn a malformed
payload into an unhandled ``TypeError``/``ValueError``, which the exception handler can
only report as a 500. That tells the client "the server failed, retry" for a request that
will never succeed, and buries genuine incidents under client-caused noise in Sentry.

Messages are in English, matching the other contract errors raised from these views: they
address whoever is building a client, and are not meant to reach an app screen.
"""

from collections.abc import Sequence
from typing import Any

from core.domain.exceptions import ValidationError


def require_object_body(data: Any) -> dict[str, Any]:
    """Return the body as a dict, or raise ``ValidationError`` if it is not one.

    Call it before ``**`` unpacking: a JSON array, string or number is valid JSON but not
    a mapping, and unpacking one raises ``TypeError`` outside the handler's reach.

    >>> require_object_body({"username": "ana"})
    {'username': 'ana'}
    """
    if isinstance(data, dict):
        return data
    raise ValidationError(f"Request body must be a JSON object, got {type(data).__name__}.")


def require_int(value: Any, field: str) -> int:
    """Coerce ``value`` to int, or raise ``ValidationError`` naming the field.

    >>> require_int("12", "song_id")
    12
    """
    try:
        return int(value)
    except (TypeError, ValueError):
        raise ValidationError(f"Field '{field}' must be an integer, got {value!r}.") from None


def require_int_list(values: Sequence[Any], field: str) -> list[int]:
    """Coerce every value of a repeated field to int, or raise ``ValidationError`` naming the
    field and the first value that is not one. Order and repeats are kept.

    >>> require_int_list(request.query_params.getlist("member_id"), "member_id")
    [12, 40]
    """
    return [require_int(value, field) for value in values]
