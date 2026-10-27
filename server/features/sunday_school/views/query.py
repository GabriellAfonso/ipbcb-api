"""The ``?year=`` query parameter shared by the public index and the panel list."""

from rest_framework.request import Request

from core.http.parsing import optional_single_value
from features.sunday_school.dtos import YearQueryDTO


def year_query(request: Request) -> int | None:
    """The year asked for, None when absent; 400 when malformed, repeated or out of range.

    >>> year_query(request)  # ?year=2026
    2026
    """
    value = optional_single_value(request.query_params.getlist("year"), "year")
    present = {} if value is None else {"year": value}
    return YearQueryDTO.model_validate(present).year
