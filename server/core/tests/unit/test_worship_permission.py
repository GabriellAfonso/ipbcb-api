from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest

from core.http import permissions as permissions_module
from core.http.permissions import IsWorshipMember

MEMBER = uuid4()


def _request(user_id: UUID, is_authenticated: bool = True) -> MagicMock:
    request = MagicMock()
    request.user.is_authenticated = is_authenticated
    request.user.pk = user_id
    return request


@pytest.fixture(autouse=True)
def _members(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(permissions_module, "_is_worship_member", lambda uid: uid == MEMBER)


def test_worship_member_is_allowed() -> None:
    assert IsWorshipMember().has_permission(_request(MEMBER), MagicMock())


def test_outsider_is_refused() -> None:
    assert not IsWorshipMember().has_permission(_request(uuid4()), MagicMock())


def test_anonymous_is_refused() -> None:
    assert not IsWorshipMember().has_permission(_request(MEMBER, False), MagicMock())


def test_message_is_the_domain_message() -> None:
    assert IsWorshipMember.message == "Disponível apenas para o ministério de Louvor."
