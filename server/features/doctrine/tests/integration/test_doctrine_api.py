import json

import pytest
from rest_framework.response import Response
from rest_framework.test import APIClient

from features.doctrine.tests.fixture_dirs import read_document, write_document
from features.doctrine.tests.integration.conftest import ServedFixtureDocuments

LIST_URL = "/api/doctrine/"
DETAIL_URL = "/api/doctrine/{slug}/"
CATECHISM = "tiny-catechism"
CONFESSION = "tiny-confession"


def _get(url: str, etag: str | None = None) -> Response:
    client = APIClient()
    response: Response = (
        client.get(url) if etag is None else client.get(url, HTTP_IF_NONE_MATCH=etag)
    )
    return response


def _body(response: Response) -> dict[str, object]:
    body: dict[str, object] = json.loads(response.content)
    return body


def _paragraphs(response: Response, chapter_index: int) -> list[dict[str, object]]:
    chapters = _body(response)["chapters"]
    assert isinstance(chapters, list)
    paragraphs: list[dict[str, object]] = chapters[chapter_index]["paragraphs"]
    return paragraphs


@pytest.mark.usefixtures("fixture_doctrine")
class TestCatechismDetail:
    def test_returns_200_without_auth(self) -> None:
        assert _get(DETAIL_URL.format(slug=CATECHISM)).status_code == 200

    def test_body_is_the_document_as_stored(self, fixture_doctrine: ServedFixtureDocuments) -> None:
        stored = read_document(fixture_doctrine.data_dir, f"{CATECHISM}.json")
        assert _body(_get(DETAIL_URL.format(slug=CATECHISM))) == stored

    def test_uninterpreted_reference_stays_null(self) -> None:
        questions = _body(_get(DETAIL_URL.format(slug=CATECHISM)))["questions"]
        assert isinstance(questions, list)
        assert questions[0]["proof_texts"][2] == {"printed": "Sl 86-8", "reference": None}

    def test_whole_chapter_reference_keeps_empty_verses(self) -> None:
        questions = _body(_get(DETAIL_URL.format(slug=CATECHISM)))["questions"]
        assert isinstance(questions, list)
        assert questions[1]["proof_texts"][0]["reference"] == {
            "book": "Sl",
            "chapter": 23,
            "verses": [],
        }

    @pytest.mark.parametrize("slug", ["nope", "Tiny-Catechism"])
    def test_unknown_or_wrong_case_slug_returns_404(self, slug: str) -> None:
        response = _get(DETAIL_URL.format(slug=slug))
        assert response.status_code == 404
        assert _body(response)["error_code"] == "NOT_FOUND"
        assert f"'{slug}'" in str(_body(response)["detail"])

    def test_post_is_not_allowed(self) -> None:
        assert APIClient().post(DETAIL_URL.format(slug=CATECHISM)).status_code == 405


@pytest.mark.usefixtures("fixture_doctrine")
class TestConfessionDetail:
    def test_chapters_and_paragraphs_in_order(self) -> None:
        response = _get(DETAIL_URL.format(slug=CONFESSION))
        chapters = _body(response)["chapters"]
        assert isinstance(chapters, list)
        assert [chapter["number"] for chapter in chapters] == [1, 2]
        assert [paragraph["number"] for paragraph in _paragraphs(response, 0)] == [1, 2]

    def test_paragraph_with_list_exposes_lists_and_text_after(self) -> None:
        paragraph = _paragraphs(_get(DETAIL_URL.format(slug=CONFESSION)), 0)[1]
        assert paragraph["lists"] == [
            {"heading": "O Velho Testamento", "items": ["Gênesis", "Êxodo"]},
            {"heading": "O Novo Testamento", "items": ["Mateus", "Marcos"]},
        ]
        assert paragraph["text_after"] == "Todos os quais foram dados por inspiração de Deus."

    def test_other_paragraphs_carry_only_number_and_text(self) -> None:
        response = _get(DETAIL_URL.format(slug=CONFESSION))
        plain = [_paragraphs(response, 0)[0], *_paragraphs(response, 1)]
        assert all(set(paragraph) == {"number", "text"} for paragraph in plain)


@pytest.mark.usefixtures("fixture_doctrine")
class TestDocumentList:
    def test_lists_documents_in_position_order(self) -> None:
        response = _get(LIST_URL)
        assert response.status_code == 200
        assert _body(response) == {
            "documents": [
                {
                    "slug": CATECHISM,
                    "title": "Catecismo de Teste",
                    "kind": "catechism",
                    "item_count": 2,
                },
                {
                    "slug": CONFESSION,
                    "title": "Confissão de Teste",
                    "kind": "confession",
                    "item_count": 2,
                },
            ]
        }

    def test_position_wins_over_file_name(self, fixture_doctrine: ServedFixtureDocuments) -> None:
        body = read_document(fixture_doctrine.data_dir, f"{CONFESSION}.json")
        write_document(
            fixture_doctrine.data_dir, "z-first.json", {**body, "slug": "z-first", "position": 0}
        )
        fixture_doctrine.reload()
        documents = _body(_get(LIST_URL))["documents"]
        assert isinstance(documents, list)
        assert [document["slug"] for document in documents] == ["z-first", CATECHISM, CONFESSION]


@pytest.mark.usefixtures("fixture_doctrine")
class TestConditionalGet:
    @pytest.mark.parametrize("url", [LIST_URL, DETAIL_URL.format(slug=CATECHISM)])
    def test_is_public_and_tagged(self, url: str) -> None:
        response = _get(url)
        assert response["ETag"]
        assert "private" not in response.get("Cache-Control", "")

    @pytest.mark.parametrize("url", [LIST_URL, DETAIL_URL.format(slug=CATECHISM)])
    def test_matching_tag_returns_304_without_body(self, url: str) -> None:
        etag = _get(url)["ETag"]
        response = _get(url, etag)
        assert response.status_code == 304
        assert response.content == b""
        assert response["ETag"] == etag

    @pytest.mark.parametrize("stale", ['"stale"', "not-a-tag", "*"])
    def test_other_tags_return_200(self, stale: str) -> None:
        assert _get(DETAIL_URL.format(slug=CATECHISM), stale).status_code == 200

    def test_text_correction_changes_the_document_tag(
        self, fixture_doctrine: ServedFixtureDocuments
    ) -> None:
        url = DETAIL_URL.format(slug=CATECHISM)
        old_etag = _get(url)["ETag"]
        self._correct_first_answer(fixture_doctrine)
        response = _get(url, old_etag)
        assert response.status_code == 200
        assert response["ETag"] != old_etag

    def test_title_correction_changes_the_list_tag(
        self, fixture_doctrine: ServedFixtureDocuments
    ) -> None:
        old_etag = _get(LIST_URL)["ETag"]
        body = read_document(fixture_doctrine.data_dir, f"{CATECHISM}.json")
        write_document(fixture_doctrine.data_dir, f"{CATECHISM}.json", {**body, "title": "Outro"})
        fixture_doctrine.reload()
        assert _get(LIST_URL, old_etag).status_code == 200

    @staticmethod
    def _correct_first_answer(fixture_doctrine: ServedFixtureDocuments) -> None:
        body = read_document(fixture_doctrine.data_dir, f"{CATECHISM}.json")
        questions = body["questions"]
        assert isinstance(questions, list)
        questions[0]["answer"] = questions[0]["answer"].replace("sempre", "sempre!")
        write_document(fixture_doctrine.data_dir, f"{CATECHISM}.json", body)
        fixture_doctrine.reload()
