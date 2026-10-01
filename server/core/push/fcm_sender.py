"""FCM HTTP v1 adapter for ``PushSender`` (specs/017-sunday-setlist-push R-05).

The only module that knows FCM exists. One request per token — v1 has no multicast — over one
authorized session, which refreshes the OAuth token itself and keeps the connection alive.
"""

from collections.abc import Mapping, Sequence
from typing import Literal, Protocol

import google.auth.exceptions
import requests

from core.application.dtos.push_dtos import PushMessage, PushSendReport

FCM_SCOPE = "https://www.googleapis.com/auth/firebase.messaging"
_SEND_URL = "https://fcm.googleapis.com/v1/projects/{project_id}/messages:send"
# (connect, read). Short on purpose: a save waits for the push, and the leader is holding the
# phone (spec 017 SC-002).
_TIMEOUT = (3.05, 5.0)
# FcmError codes meaning "this token will never work again". A bare 404 is not enough: a wrong
# project id answers 404 for every token, and deleting on it would wipe the table.
_DEAD_TOKEN_CODES = frozenset({"UNREGISTERED", "NOT_FOUND"})
# Credentials or project are wrong: every remaining token would fail the same way.
_CONFIG_ERROR_STATUSES = frozenset({401, 403})
# Network down, timeout, or the OAuth refresh failing: stop instead of waiting once per token.
_TRANSPORT_ERRORS = (requests.RequestException, google.auth.exceptions.GoogleAuthError)

TokenOutcome = Literal["sent", "invalid", "failed", "abort"]


class HttpResponse(Protocol):
    status_code: int

    def json(self) -> object: ...


class HttpSession(Protocol):
    """What the sender needs from ``google.auth.transport.requests.AuthorizedSession``."""

    def post(
        self, url: str, *, json: Mapping[str, object], timeout: tuple[float, float]
    ) -> HttpResponse: ...


class FcmPushSender:
    """Sends data messages through FCM HTTP v1.

    >>> FcmPushSender(AuthorizedSession(credentials), "ipbcb-app").send(["t1"], message).sent
    1
    """

    def __init__(self, session: HttpSession, project_id: str) -> None:
        self._session = session
        self._url = _SEND_URL.format(project_id=project_id)

    def send(self, tokens: Sequence[str], message: PushMessage) -> PushSendReport:
        report = PushSendReport()
        for index, token in enumerate(tokens):
            outcome = self._send_one(token, message)
            if outcome == "abort":
                report.aborted = True
                report.failed += len(tokens) - index
                break
            _record(report, token, outcome)
        return report

    def _send_one(self, token: str, message: PushMessage) -> TokenOutcome:
        try:
            response = self._session.post(self._url, json=_body(token, message), timeout=_TIMEOUT)
        except _TRANSPORT_ERRORS:
            return "abort"
        return classify_response(response)


def _record(report: PushSendReport, token: str, outcome: TokenOutcome) -> None:
    if outcome == "sent":
        report.sent += 1
    elif outcome == "invalid":
        report.invalid_tokens.append(token)
    else:
        report.failed += 1


def _body(token: str, message: PushMessage) -> dict[str, object]:
    # HIGH: a data-only message at normal priority can be held for a dozing phone (SC-001).
    return {"message": {"token": token, "data": message.as_data(), "android": {"priority": "HIGH"}}}


def classify_response(response: HttpResponse) -> TokenOutcome:
    """What one FCM answer means for its token.

    >>> unregistered = {"error": {"details": [{"errorCode": "UNREGISTERED"}]}}
    >>> classify_response(FakeHttpResponse(404, unregistered))
    'invalid'
    """
    if response.status_code == 200:
        return "sent"
    if response.status_code in _CONFIG_ERROR_STATUSES:
        return "abort"
    if _fcm_error_codes(response) & _DEAD_TOKEN_CODES:
        return "invalid"
    return "failed"


def _fcm_error_codes(response: HttpResponse) -> set[str]:
    """``errorCode`` of each FcmError in ``error.details``; empty for an unreadable body."""
    try:
        body = response.json()
    except ValueError:
        return set()
    error = body.get("error") if isinstance(body, dict) else None
    details = error.get("details") if isinstance(error, dict) else None
    if not isinstance(details, list):
        return set()
    return {d["errorCode"] for d in details if isinstance(d, dict) and "errorCode" in d}
