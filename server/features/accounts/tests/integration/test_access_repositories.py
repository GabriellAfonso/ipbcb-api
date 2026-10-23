"""Access-request and managed-account repositories against the database
(specs/022-access-requests data-model.md)."""

from datetime import timedelta

import pytest
from django.utils import timezone

from conftest import make_user
from core.domain.exceptions import (
    AccessRequestNotFoundError,
    AccessRequestNotPendingError,
    AccessRequestPendingError,
)
from features.accounts.domain.access_requests import AccessRequestStatus, AccessRequestType
from features.accounts.dtos import AccessDecisionDTO, AccessGrantDTO, AccessRequestCreateDTO
from features.accounts.models.access_request import AccessRequest
from features.accounts.repositories.access_request_repository import AccessRequestRepositoryImpl
from features.accounts.repositories.managed_account_repository import ManagedAccountRepositoryImpl

pytestmark = pytest.mark.django_db

ACCESS = AccessRequestCreateDTO(type=AccessRequestType.ACCESS)


@pytest.fixture
def repository() -> AccessRequestRepositoryImpl:
    return AccessRequestRepositoryImpl()


class TestAccessRequestRepository:
    def test_create_and_pending_types(self, repository: AccessRequestRepositoryImpl) -> None:
        user = make_user(username="ana")
        record = repository.create(user.pk, ACCESS)
        assert record.status is AccessRequestStatus.PENDING
        assert repository.pending_types(user.pk) == {AccessRequestType.ACCESS}
        assert repository.latest_created_at(user.pk) == record.created_at
        assert repository.pending_id(user.pk, AccessRequestType.ACCESS) == record.id
        assert repository.pending_id(user.pk, AccessRequestType.DATA_CORRECTION) is None

    def test_second_pending_of_same_type_is_refused_by_the_store(
        self, repository: AccessRequestRepositoryImpl
    ) -> None:
        user = make_user(username="ana")
        repository.create(user.pk, ACCESS)
        with pytest.raises(AccessRequestPendingError):
            repository.create(user.pk, ACCESS)
        assert AccessRequest.objects.count() == 1

    def test_decided_request_frees_the_type(self, repository: AccessRequestRepositoryImpl) -> None:
        user = make_user(username="ana")
        AccessRequest.objects.create(user=user, type="access", status="denied")
        repository.create(user.pk, ACCESS)
        assert AccessRequest.objects.count() == 2

    def test_decide_once(self, repository: AccessRequestRepositoryImpl) -> None:
        user = make_user(username="ana")
        leader = make_user(username="leader")
        record = repository.create(user.pk, ACCESS)
        decision = AccessDecisionDTO(
            status=AccessRequestStatus.DENIED,
            decided_by=leader.pk,
            decided_at=timezone.now(),
            denial_reason="Não.",
        )
        decided = repository.decide(record.id, decision)
        assert decided.decided_by is not None and decided.decided_by.id == leader.pk
        with pytest.raises(AccessRequestNotPendingError):
            repository.decide(record.id, decision)
        with pytest.raises(AccessRequestNotFoundError):
            repository.decide(999, decision)

    def test_history_newest_first(self, repository: AccessRequestRepositoryImpl) -> None:
        user = make_user(username="ana")
        old = AccessRequest.objects.create(user=user, type="access", status="denied")
        AccessRequest.objects.filter(pk=old.pk).update(
            created_at=timezone.now() - timedelta(days=2)
        )
        new = AccessRequest.objects.create(user=user, type="access")
        assert [r.id for r in repository.list_for_user(user.pk)] == [new.pk, old.pk]

    def test_account_deletion(self, repository: AccessRequestRepositoryImpl) -> None:
        user = make_user(username="ana")
        leader = make_user(username="leader")
        decided = AccessRequest.objects.create(
            user=make_user(username="bia"), type="access", status="approved", decided_by=leader
        )
        AccessRequest.objects.create(user=user, type="access")

        user.delete()
        leader.delete()

        assert AccessRequest.objects.filter(user_id=user.pk).count() == 0
        decided.refresh_from_db()
        assert decided.decided_by is None
        assert decided.status == "approved"


class TestManagedAccountRepository:
    def test_flags_of_an_account_without_profile_row(self) -> None:
        user = make_user(username="ana")
        user.profile.delete()
        flags = ManagedAccountRepositoryImpl().access_flags(user.pk)
        assert flags.member_access is False and flags.access_requests_blocked is False

    def test_grant_and_revoke_member_access(self) -> None:
        user = make_user(username="ana")
        leader = make_user(username="leader")
        grant = AccessGrantDTO(granted_by=leader.pk, granted_at=timezone.now())
        repository = ManagedAccountRepositoryImpl()

        repository.grant_member_access(user.pk, grant)
        account = repository.get_account(user.pk)
        assert account is not None and account.member_access is True
        assert account.access_granted_by is not None
        assert account.access_granted_by.id == leader.pk
        assert account.access_granted_at == grant.granted_at

        repository.revoke_member_access(user.pk)
        user.profile.refresh_from_db()
        assert user.profile.member_access is False
        assert user.profile.access_granted_by is None
        assert user.profile.access_granted_at is None
