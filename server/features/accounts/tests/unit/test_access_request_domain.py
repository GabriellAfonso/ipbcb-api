"""Pure rules, DTOs and exceptions of access requests (specs/022-access-requests)."""

from datetime import UTC, datetime, timedelta

import pytest

from core.domain.access import Role, has_member_access
from core.domain.exceptions import (
    AccessRequestMessageRequiredError,
    AccessRequestNotPendingError,
    AccessRequestPendingError,
    AccessRequestRateLimitedError,
    AccessRequestsBlockedError,
    MemberAccessAlreadyGrantedError,
    MemberNotLinkedError,
    RollMemberAlreadyLinkedError,
    RollMemberNotFoundError,
)
from core.http.exceptions import custom_exception_handler
from features.accounts.domain.access_requests import (
    AccessRequestType,
    AccessStatus,
    access_status,
    clean_text,
    seconds_until_next_request,
)
from features.accounts.dtos import AccessRequestCreateDTO, ManagedAccountPatchDTO

ASKED = datetime(2026, 10, 21, 12, tzinfo=UTC)


@pytest.mark.parametrize(
    ("flag", "roles", "expected"),
    [
        (True, [], True),
        (False, [], False),
        (False, [Role.ADMIN], True),
        (False, [Role.LEADER], True),
        (False, [Role.MEDIA], False),
        (False, [Role.MEDIA, Role.LEADER], True),
    ],
)
def test_has_member_access(flag: bool, roles: list[Role], expected: bool) -> None:
    assert has_member_access(flag, roles) is expected


@pytest.mark.parametrize(
    ("member_access", "pending", "expected"),
    [
        (True, True, AccessStatus.GRANTED),
        (False, True, AccessStatus.PENDING),
        (False, False, AccessStatus.NONE),
    ],
)
def test_access_status(member_access: bool, pending: bool, expected: AccessStatus) -> None:
    assert access_status(member_access, pending) is expected


@pytest.mark.parametrize(
    ("elapsed", "expected"),
    [
        (timedelta(0), 86400),
        (timedelta(hours=23), 3600),
        (timedelta(hours=23, minutes=59, seconds=59, milliseconds=500), 1),
        (timedelta(hours=24), 0),
        (timedelta(days=3), 0),
    ],
)
def test_seconds_until_next_request(elapsed: timedelta, expected: int) -> None:
    assert seconds_until_next_request(ASKED, ASKED + elapsed) == expected


def test_no_previous_request_may_ask_now() -> None:
    assert seconds_until_next_request(None, ASKED) == 0


@pytest.mark.parametrize(("raw", "expected"), [(None, None), ("  ", None), (" a ", "a")])
def test_clean_text(raw: str | None, expected: str | None) -> None:
    assert clean_text(raw) == expected


def test_create_dto_trims_the_message() -> None:
    assert AccessRequestCreateDTO(type=AccessRequestType.ACCESS, message="  oi ").message == "oi"


def test_patch_dto_tells_absent_from_null() -> None:
    assert ManagedAccountPatchDTO().model_fields_set == set()
    assert ManagedAccountPatchDTO(member_id=None).model_fields_set == {"member_id"}


@pytest.mark.parametrize(
    ("error", "status", "code"),
    [
        (AccessRequestsBlockedError(), 403, "ACCESS_REQUESTS_BLOCKED"),
        (MemberAccessAlreadyGrantedError(), 409, "MEMBER_ACCESS_ALREADY_GRANTED"),
        (AccessRequestPendingError("access"), 409, "ACCESS_REQUEST_PENDING"),
        (AccessRequestRateLimitedError(60), 429, "ACCESS_REQUEST_RATE_LIMITED"),
        (AccessRequestMessageRequiredError(), 400, "VALIDATION_ERROR"),
        (AccessRequestNotPendingError(1, "approved"), 409, "ACCESS_REQUEST_NOT_PENDING"),
        (RollMemberNotFoundError(9), 400, "VALIDATION_ERROR"),
        (RollMemberAlreadyLinkedError(9), 409, "MEMBER_ALREADY_LINKED"),
        (MemberNotLinkedError(), 404, "MEMBER_NOT_LINKED"),
    ],
)
def test_exceptions_map_to_the_contract(error: Exception, status: int, code: str) -> None:
    response = custom_exception_handler(error, {})
    assert response is not None
    assert response.status_code == status
    assert response.data["error_code"] == code
    assert isinstance(response.data["detail"], str)


def test_rate_limit_says_how_long_to_wait() -> None:
    response = custom_exception_handler(AccessRequestRateLimitedError(3600), {})
    assert response is not None
    assert response.data["retry_after_seconds"] == 3600


def test_field_errors_name_the_field() -> None:
    response = custom_exception_handler(RollMemberNotFoundError(9), {})
    assert response is not None
    assert list(response.data["field_errors"]) == ["member_id"]
