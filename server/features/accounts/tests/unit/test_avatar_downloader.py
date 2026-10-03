import pytest
import requests

from features.accounts.repositories.avatar_downloader import HttpAvatarDownloader
from features.accounts.tests.fakes import FakeHttpResponse

URL = "https://lh3.googleusercontent.com/a/x=s400-c"


def test_returns_body_of_a_200(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(requests, "get", lambda url, timeout: FakeHttpResponse(200, b"img"))

    assert HttpAvatarDownloader().download(URL) == b"img"


def test_non_200_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(requests, "get", lambda url, timeout: FakeHttpResponse(404))

    assert HttpAvatarDownloader().download(URL) is None


def test_network_error_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    def unreachable(url: str, timeout: int) -> FakeHttpResponse:
        raise requests.ConnectionError("no route")

    monkeypatch.setattr(requests, "get", unreachable)

    assert HttpAvatarDownloader().download(URL) is None


def test_download_is_bounded_by_a_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    seen_timeouts: list[int] = []

    def recording_get(url: str, timeout: int) -> FakeHttpResponse:
        seen_timeouts.append(timeout)
        return FakeHttpResponse(200, b"img")

    monkeypatch.setattr(requests, "get", recording_get)

    HttpAvatarDownloader().download(URL)

    assert seen_timeouts == [5]
