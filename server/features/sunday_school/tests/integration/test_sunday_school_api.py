"""Sunday school over HTTP with the ORM repositories and the real Bible data
(specs/026-sunday-school US1–US4). The 2026 lessons the data migration loads are removed first,
so each test starts from an empty domain."""

from typing import Any

import pytest
from rest_framework.test import APIClient

from conftest import make_member_client, make_role_client
from core.domain.access import Role
from features.sunday_school.models import SundaySchoolLesson, SundaySchoolYear
from features.sunday_school.tests.fakes import proof, sample_content

INDEX_URL = "/api/sunday-school/"
LESSONS_URL = "/api/sunday-school/manage/lessons/"
ORDER_URL = "/api/sunday-school/manage/lessons/order/"
YEARS_URL = "/api/sunday-school/manage/years/"

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _empty_domain() -> None:
    SundaySchoolLesson.objects.all().delete()
    SundaySchoolYear.objects.all().delete()


@pytest.fixture
def leader() -> APIClient:
    client, _ = make_role_client(Role.LEADER, username="lider")
    return client


def _lesson_url(lesson_id: int, manage: bool = False) -> str:
    prefix = "/api/sunday-school/manage/lessons/" if manage else "/api/sunday-school/lessons/"
    return f"{prefix}{lesson_id}/"


def _create(client: APIClient, **fields: Any) -> Any:
    body = {"year": 2026, "title": "Panorama", "status": "published", "content": sample_content()}
    return client.post(LESSONS_URL, {**body, **fields}, format="json")


class TestPublic:
    def test_index_lesson_and_etag(self, leader: APIClient) -> None:
        a = _create(leader, title="Josué").data
        _create(leader, title="Rute", status="draft")
        anonymous = APIClient()

        index = anonymous.get(INDEX_URL)
        lesson = anonymous.get(_lesson_url(a["id"]))
        again = anonymous.get(INDEX_URL, HTTP_IF_NONE_MATCH=index["ETag"])

        assert index.data["default_year"] == 2026
        assert [x["title"] for x in index.data["lessons"]] == ["Josué"]
        assert lesson.data["year"] == {"year": 2026, "theme": ""}
        assert lesson.data["content"] == a["content"]
        assert again.status_code == 304
        assert "Cache-Control" not in index

    def test_unpublished_year_and_draft_are_404(self, leader: APIClient) -> None:
        draft = _create(leader, year=2027, status="draft").data

        year = APIClient().get(INDEX_URL, {"year": 2027})
        lesson = APIClient().get(_lesson_url(draft["id"]))

        assert (year.status_code, year.data["error_code"]) == (404, "SUNDAY_SCHOOL_YEAR_NOT_FOUND")
        assert lesson.data["error_code"] == "SUNDAY_SCHOOL_LESSON_NOT_FOUND"

    @pytest.mark.parametrize("year", ["abc", "1999"])
    def test_malformed_year_is_400(self, year: str) -> None:
        assert APIClient().get(INDEX_URL, {"year": year}).status_code == 400

    def test_book_facts_from_real_bible(self, leader: APIClient) -> None:
        content = {"sections": [{"title": "S", "blocks": [{"type": "book_facts", "book": "Mc"}]}]}
        created = _create(leader, content=content).data

        books = APIClient().get(_lesson_url(created["id"])).data["books"]

        assert books["Mc"] == {"name": "Marcos", "position": 41, "chapters": 16, "verses": 678}


class TestManage:
    def test_create_creates_year_and_records_author(self, leader: APIClient) -> None:
        response = _create(leader, year=2028)

        assert response.status_code == 201
        assert SundaySchoolYear.objects.get(year=2028).theme == ""
        assert SundaySchoolLesson.objects.get().created_by is not None

    def test_content_error_names_path(self, leader: APIClient) -> None:
        response = _create(leader, content=sample_content(proof_texts=[proof("Dn", 13, 1)]))

        assert response.status_code == 400
        assert response.data["error_code"] == "SUNDAY_SCHOOL_CONTENT_INVALID"
        assert response.data["errors"][0]["path"] == "sections.0.blocks.0.proof_texts.0.reference"
        assert not SundaySchoolLesson.objects.exists()

    def test_authors_in_body_are_refused(self, leader: APIClient) -> None:
        response = _create(leader, created_by=None)

        assert (response.status_code, response.data["error_code"]) == (400, "VALIDATION_ERROR")

    def test_list_includes_drafts_and_is_private(self, leader: APIClient) -> None:
        _create(leader, status="draft")

        response = leader.get(LESSONS_URL, {"year": 2026})

        assert [x["status"] for x in response.data] == ["draft"]
        assert response["Cache-Control"] == "private, no-store"
        assert leader.get(LESSONS_URL).status_code == 400

    def test_patch_publish_and_move(self, leader: APIClient) -> None:
        a = _create(leader, title="A", status="draft").data
        b = _create(leader, title="B").data

        published = leader.patch(_lesson_url(a["id"], True), {"status": "published"}, format="json")
        moved = leader.patch(_lesson_url(a["id"], True), {"year": 2027}, format="json")

        assert published.data["status"] == "published"
        assert (moved.data["year"]["year"], moved.data["position"]) == (2027, 0)
        assert SundaySchoolLesson.objects.get(pk=b["id"]).position == 0

    def test_order_delete_and_theme(self, leader: APIClient) -> None:
        ids = [_create(leader, title=t).data["id"] for t in "ABC"]

        order = leader.put(ORDER_URL, {"year": 2026, "lesson_ids": ids[::-1]}, format="json")
        mismatch = leader.put(ORDER_URL, {"year": 2026, "lesson_ids": ids[:2]}, format="json")
        deleted = leader.delete(_lesson_url(ids[2], True))
        theme = leader.patch(f"{YEARS_URL}2026/", {"theme": "O Drama"}, format="json")

        assert (order.status_code, deleted.status_code) == (204, 204)
        assert mismatch.data["error_code"] == "SUNDAY_SCHOOL_ORDER_MISMATCH"
        titles = [x["title"] for x in leader.get(LESSONS_URL, {"year": 2026}).data]
        assert titles == ["B", "A"]
        assert theme.data == {
            "year": 2026,
            "theme": "O Drama",
            "lesson_count": 2,
            "published_count": 2,
        }
        assert leader.get(YEARS_URL).data[0]["year"] == 2026

    def test_unknown_year_theme_is_404(self, leader: APIClient) -> None:
        response = leader.patch(f"{YEARS_URL}2030/", {"theme": ""}, format="json")

        assert response.data["error_code"] == "SUNDAY_SCHOOL_YEAR_NOT_FOUND"

    def test_media_and_members_are_403(self) -> None:
        media, _ = make_role_client(Role.MEDIA, username="midia")
        member, _ = make_member_client()

        assert _create(media).status_code == 403
        assert member.get(YEARS_URL).status_code == 403
        assert _create(APIClient()).status_code == 401
