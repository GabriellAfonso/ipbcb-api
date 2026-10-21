"""Shared setup for the access-request integration tests (specs/022-access-requests)."""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime

from dependency_injector import providers

from config.di import Container
from core.models.device_token import DeviceToken
from core.tests.fakes import FakePushSender
from features.accounts.models.user import User
from features.accounts.tests.access_fakes import FixedClock

ME_REQUESTS_URL = "/api/me/access-requests/"
PROFILES_URL = "/api/admin/profiles/"
PROFILE_URL = "/api/me/profile/"


def account_url(user: User, action: str = "") -> str:
    """>>> account_url(ana, "revoke-access/")
    '/api/admin/profiles/5b0e.../revoke-access/'
    """
    return f"{PROFILES_URL}{user.pk}/{action}"


def decision_url(request_id: int, decision: str) -> str:
    return f"{PROFILES_URL}requests/{request_id}/{decision}/"


def register_device(user: User, token: str) -> None:
    DeviceToken.objects.create(token=token, user=user)


def tokens_messaged(sender: FakePushSender) -> list[tuple[set[str], dict[str, str]]]:
    """Each send as (tokens, payload)."""
    return [(set(tokens), message.as_data()) for tokens, message in sender.calls]


@contextmanager
def frozen_at(container: Container, moment: datetime) -> Iterator[None]:
    """Freeze the services' clock. ``created_at`` is stamped by the database, so tests that
    need an old request rewrite it with ``AccessRequest.objects.update``."""
    with container.clock.override(providers.Object(FixedClock(moment))):
        yield
