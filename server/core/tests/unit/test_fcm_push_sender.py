from collections.abc import Mapping
from datetime import date

import requests

from core.application.dtos.push_dtos import PushMessage, PushSendReport
from core.domain.push import PushMessageType
from core.push.fcm_sender import FcmPushSender, classify_response

MESSAGE = PushMessage(type=PushMessageType.SETLIST_SAVED, date=date(2026, 10, 4))
UNREGISTERED = {"error": {"status": "NOT_FOUND", "details": [{"errorCode": "UNREGISTERED"}]}}


class FakeHttpResponse:
    def __init__(self, status_code: int, body: object = None) -> None:
        self.status_code = status_code
        self._body = body

    def json(self) -> object:
        if self._body is None:
            raise ValueError("no JSON body")
        return self._body


class FakeHttpSession:
    """Answers each post from a per-token script; a script entry that is an exception is raised."""

    def __init__(self, answers: Mapping[str, FakeHttpResponse | Exception]) -> None:
        self.answers = answers
        self.posts: list[tuple[str, Mapping[str, object], tuple[float, float]]] = []

    def post(
        self, url: str, *, json: Mapping[str, object], timeout: tuple[float, float]
    ) -> FakeHttpResponse:
        self.posts.append((url, json, timeout))
        message = json["message"]
        assert isinstance(message, dict)
        answer = self.answers[message["token"]]
        if isinstance(answer, Exception):
            raise answer
        return answer


def _send(
    answers: Mapping[str, FakeHttpResponse | Exception],
) -> tuple[PushSendReport, FakeHttpSession]:
    session = FakeHttpSession(answers)
    report = FcmPushSender(session, "ipbcb-app").send(list(answers), MESSAGE)
    return report, session


def test_success_counts_as_sent() -> None:
    report, _ = _send({"t1": FakeHttpResponse(200, {"name": "x"})})
    assert report.sent == 1 and report.failed == 0 and not report.aborted


def test_unregistered_token_is_invalid() -> None:
    report, _ = _send({"t1": FakeHttpResponse(404, UNREGISTERED)})
    assert report.invalid_tokens == ["t1"]


def test_bare_404_is_not_invalid() -> None:
    # A wrong project id answers 404 too; deleting on it would wipe every token.
    assert classify_response(FakeHttpResponse(404, {"error": {"status": "NOT_FOUND"}})) == "failed"


def test_invalid_argument_keeps_the_token() -> None:
    body = {"error": {"details": [{"errorCode": "INVALID_ARGUMENT"}]}}
    assert classify_response(FakeHttpResponse(400, body)) == "failed"


def test_server_error_is_failed() -> None:
    assert classify_response(FakeHttpResponse(500)) == "failed"


def test_auth_error_aborts() -> None:
    assert classify_response(FakeHttpResponse(403, {"error": {}})) == "abort"


def test_timeout_aborts_the_rest_of_the_batch() -> None:
    report, session = _send(
        {
            "t1": FakeHttpResponse(200, {}),
            "t2": requests.Timeout("slow"),
            "t3": FakeHttpResponse(200, {}),
            "t4": FakeHttpResponse(200, {}),
        }
    )
    assert report.sent == 1 and report.failed == 3 and report.aborted
    assert len(session.posts) == 2


def test_request_body_shape() -> None:
    _, session = _send({"t1": FakeHttpResponse(200, {})})
    url, body, timeout = session.posts[0]
    assert url == "https://fcm.googleapis.com/v1/projects/ipbcb-app/messages:send"
    assert body == {
        "message": {
            "token": "t1",
            "data": {"type": "setlist_saved", "date": "2026-10-04"},
            "android": {"priority": "HIGH"},
        }
    }
    assert timeout == (3.05, 5.0)
