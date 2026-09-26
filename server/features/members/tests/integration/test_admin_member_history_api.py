"""Edit history as the app reads it (US3)."""

import pytest
from rest_framework.test import APIClient

from conftest import make_admin_client, make_member_client
from features.members.models.member import Member, Ministry


def history_url(member_id: int) -> str:
    return f"/api/admin/members/{member_id}/history/"


@pytest.mark.django_db
class TestAccess:
    def test_anonymous_401(self) -> None:
        member = Member.objects.create(name="Ana")
        assert APIClient().get(history_url(member.pk)).status_code == 401

    def test_plain_member_403(self) -> None:
        member = Member.objects.create(name="Ana")
        client, _ = make_member_client()
        assert client.get(history_url(member.pk)).status_code == 403

    def test_unknown_member_404(self) -> None:
        client, _ = make_admin_client()
        assert client.get(history_url(999)).status_code == 404


@pytest.mark.django_db
class TestHistory:
    def test_create_then_edits_newest_first(self) -> None:
        louvor = Ministry.objects.create(name="Louvor")
        acao = Ministry.objects.create(name="Ação social")
        recepcao = Ministry.objects.create(name="Recepção")
        client, leader = make_admin_client()
        leader.profile.name = "Pr. João"
        leader.profile.save()
        member_id = client.post(
            "/api/admin/members/",
            {"name": "Ana", "ministry_ids": [louvor.pk, acao.pk]},
            format="json",
        ).data["id"]
        client.patch(
            f"/api/admin/members/{member_id}/",
            {"gender": "F", "ministry_ids": [louvor.pk, recepcao.pk]},
            format="json",
        )

        response = client.get(history_url(member_id))

        assert response.status_code == 200
        history = response.data["history"]
        assert [e["field"] for e in history] == ["ministries", "gender", "created"]
        assert history[0]["old_value"] == "Ação social, Louvor"
        assert history[0]["new_value"] == "Louvor, Recepção"
        assert history[1]["old_value"] is None and history[1]["new_value"] == "F"
        assert history[0]["editor"] == {"id": str(leader.pk), "name": "Pr. João"}
        assert set(history[0]) == {"id", "editor", "field", "old_value", "new_value", "changed_at"}

    def test_reads_are_not_recorded(self) -> None:
        client, _ = make_admin_client()
        member_id = client.post("/api/admin/members/", {"name": "Ana"}, format="json").data["id"]

        client.get(f"/api/admin/members/{member_id}/")
        client.get(history_url(member_id))

        assert len(client.get(history_url(member_id)).data["history"]) == 1

    def test_private_cache_and_304(self) -> None:
        client, _ = make_admin_client()
        member_id = client.post("/api/admin/members/", {"name": "Ana"}, format="json").data["id"]

        first = client.get(history_url(member_id))
        second = client.get(history_url(member_id), HTTP_IF_NONE_MATCH=first["ETag"])

        assert first["Cache-Control"] == "private, no-store"
        assert "Authorization" in first["Vary"]
        assert second.status_code == 304
