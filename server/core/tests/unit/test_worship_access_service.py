from uuid import UUID, uuid4

import pytest

from core.application.access_service import AccessService
from core.application.dtos.access_dtos import AccessGrantsDTO
from core.application.worship_access_service import WorshipAccessService
from core.domain.access import Level, Role, Scope
from core.domain.exceptions import NotWorshipMemberError
from core.tests.fakes import FakeRoleGrantRepository, FakeWorshipMembership

ANA, BIA, CAIO = uuid4(), uuid4(), uuid4()
SONGS_MANAGER = AccessGrantsDTO(roles=[Role.LEADER], levels={Scope.SONGS: Level.MANAGE})
NO_ROLE = AccessGrantsDTO(roles=[], levels={})


def _service(
    members: set[UUID], holders: set[UUID] | None = None, ministry_exists: bool = True
) -> WorshipAccessService:
    access = AccessService(FakeRoleGrantRepository([], [], level_holders=holders))
    membership = FakeWorshipMembership(members, ministry_exists)
    return WorshipAccessService(membership, access)


class TestFlags:
    def test_manager_in_worship_can_save(self) -> None:
        flags = _service({ANA}).flags_for(ANA, SONGS_MANAGER)
        assert flags.is_worship_member and flags.can_save_setlist

    def test_worship_member_without_level_cannot_save(self) -> None:
        flags = _service({ANA}).flags_for(ANA, NO_ROLE)
        assert flags.is_worship_member and not flags.can_save_setlist

    def test_manager_outside_worship_has_neither(self) -> None:
        flags = _service(set()).flags_for(ANA, SONGS_MANAGER)
        assert not flags.is_worship_member and not flags.can_save_setlist

    def test_view_level_is_not_enough(self) -> None:
        viewer = AccessGrantsDTO(roles=[Role.MEDIA], levels={Scope.SONGS: Level.VIEW})
        assert not _service({ANA}).flags_for(ANA, viewer).can_save_setlist


class TestEnsureWorshipMember:
    def test_member_passes(self) -> None:
        _service({ANA}).ensure_worship_member(ANA)

    def test_outsider_is_refused(self) -> None:
        with pytest.raises(NotWorshipMemberError):
            _service({ANA}).ensure_worship_member(BIA)


class TestRecipients:
    def test_setlist_recipients_are_every_worship_member(self) -> None:
        assert _service({ANA, BIA}, holders={CAIO}).setlist_recipients() == {ANA, BIA}

    def test_reminder_recipients_are_managers_in_worship(self) -> None:
        service = _service({ANA, BIA}, holders={BIA, CAIO})
        assert service.reminder_recipients() == {BIA}

    def test_missing_ministry_is_logged(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level("WARNING"):
            assert _service(set(), ministry_exists=False).setlist_recipients() == set()
        assert [r.getMessage() for r in caplog.records] == ["worship_ministry_missing"]

    def test_existing_ministry_logs_nothing(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level("WARNING"):
            _service({ANA}).reminder_recipients()
        assert caplog.records == []
