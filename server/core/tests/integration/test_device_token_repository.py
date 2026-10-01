import pytest

from conftest import make_user
from core.models import DeviceToken
from core.repositories.device_token_repository import DeviceTokenRepositoryImpl


@pytest.mark.django_db
class TestDeviceTokenRepository:
    repository = DeviceTokenRepositoryImpl()

    def test_register_is_idempotent(self) -> None:
        ana = make_user(username="ana")
        self.repository.register(ana.pk, "t1")
        self.repository.register(ana.pk, "t1")
        assert list(DeviceToken.objects.values_list("token", "user_id")) == [("t1", ana.pk)]

    def test_register_moves_token_to_new_owner(self) -> None:
        ana, bia = make_user(username="ana"), make_user(username="bia")
        self.repository.register(ana.pk, "t1")
        self.repository.register(bia.pk, "t1")
        assert DeviceToken.objects.get(token="t1").user_id == bia.pk
        assert DeviceToken.objects.count() == 1

    def test_unregister_only_by_owner(self) -> None:
        ana, bia = make_user(username="ana"), make_user(username="bia")
        self.repository.register(ana.pk, "t1")
        self.repository.unregister(bia.pk, "t1")
        assert DeviceToken.objects.filter(token="t1").exists()
        self.repository.unregister(ana.pk, "t1")
        assert not DeviceToken.objects.exists()

    def test_unregister_unknown_token_changes_nothing(self) -> None:
        ana = make_user(username="ana")
        self.repository.unregister(ana.pk, "never-seen")
        assert not DeviceToken.objects.exists()

    def test_tokens_for_selected_users_only(self) -> None:
        ana, bia, caio = (make_user(username=n) for n in ("ana", "bia", "caio"))
        self.repository.register(ana.pk, "a1")
        self.repository.register(ana.pk, "a2")
        self.repository.register(bia.pk, "b1")
        self.repository.register(caio.pk, "c1")
        assert sorted(self.repository.tokens_for({ana.pk, bia.pk})) == ["a1", "a2", "b1"]
        assert self.repository.tokens_for(set()) == []

    def test_delete_tokens_counts_removed(self) -> None:
        ana = make_user(username="ana")
        self.repository.register(ana.pk, "a1")
        self.repository.register(ana.pk, "a2")
        assert self.repository.delete_tokens(["a1", "missing"]) == 1
        assert self.repository.tokens_for({ana.pk}) == ["a2"]

    def test_tokens_go_with_their_user(self) -> None:
        ana = make_user(username="ana")
        self.repository.register(ana.pk, "a1")
        ana.delete()
        assert not DeviceToken.objects.exists()

    def test_str_hides_the_token(self) -> None:
        ana = make_user(username="ana")
        self.repository.register(ana.pk, "secret-token")
        assert "secret-token" not in str(DeviceToken.objects.get())
