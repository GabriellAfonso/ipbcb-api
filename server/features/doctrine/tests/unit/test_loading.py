import re
from pathlib import Path

import pytest

from features.doctrine.loading import DoctrineDataError, load_doctrine_documents
from features.doctrine.tests.fixture_dirs import copy_fixture_dir, read_document, write_document

CATECHISM_FILE = "tiny-catechism.json"
CONFESSION_FILE = "tiny-confession.json"


def _questions(body: dict[str, object]) -> list[dict[str, object]]:
    questions = body["questions"]
    assert isinstance(questions, list)
    return questions


def _first_chapter_paragraphs(body: dict[str, object]) -> list[dict[str, object]]:
    chapters = body["chapters"]
    assert isinstance(chapters, list)
    paragraphs: list[dict[str, object]] = chapters[0]["paragraphs"]
    return paragraphs


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    return copy_fixture_dir("valid", tmp_path)


class TestValidData:
    def test_loads_documents_ordered_by_position(self, data_dir: Path) -> None:
        slugs = [document.slug for document in load_doctrine_documents(data_dir)]
        assert slugs == ["tiny-catechism", "tiny-confession"]

    def test_empty_dir_loads_nothing(self, tmp_path: Path) -> None:
        assert load_doctrine_documents(tmp_path) == []

    def test_position_wins_over_file_name(self, data_dir: Path) -> None:
        body = read_document(data_dir, CONFESSION_FILE)
        write_document(data_dir, CONFESSION_FILE, {**body, "position": 0})
        slugs = [document.slug for document in load_doctrine_documents(data_dir)]
        assert slugs == ["tiny-confession", "tiny-catechism"]


class TestNumbering:
    @pytest.mark.parametrize(
        ("numbers", "message"),
        [
            ([1, 3], "questions[1].number is 3; expected 2"),
            ([1, 1], "questions[1].number is 1; expected 2"),
            ([0, 1], "questions[0].number is 0; expected 1"),
        ],
    )
    def test_rejects_non_contiguous_questions(
        self, data_dir: Path, numbers: list[int], message: str
    ) -> None:
        body = read_document(data_dir, CATECHISM_FILE)
        for question, number in zip(_questions(body), numbers):
            question["number"] = number
        write_document(data_dir, CATECHISM_FILE, body)
        with pytest.raises(DoctrineDataError, match=re.escape(f"{CATECHISM_FILE}: {message}")):
            load_doctrine_documents(data_dir)

    def test_rejects_gap_in_chapter_paragraphs(self, data_dir: Path) -> None:
        body = read_document(data_dir, CONFESSION_FILE)
        _first_chapter_paragraphs(body)[1]["number"] = 5
        write_document(data_dir, CONFESSION_FILE, body)
        with pytest.raises(DoctrineDataError, match=r"chapters\[0\]\.paragraphs\[1\]\.number is 5"):
            load_doctrine_documents(data_dir)

    def test_rejects_document_without_items(self, data_dir: Path) -> None:
        body = read_document(data_dir, CATECHISM_FILE)
        write_document(data_dir, CATECHISM_FILE, {**body, "questions": []})
        with pytest.raises(DoctrineDataError, match="questions is empty"):
            load_doctrine_documents(data_dir)


class TestIdentity:
    def test_rejects_slug_different_from_file_name(self, data_dir: Path) -> None:
        body = read_document(data_dir, CATECHISM_FILE)
        write_document(data_dir, CATECHISM_FILE, {**body, "slug": "other-catechism"})
        with pytest.raises(DoctrineDataError, match="'other-catechism'; expected 'tiny-catechism'"):
            load_doctrine_documents(data_dir)

    def test_rejects_uppercase_slug(self, data_dir: Path) -> None:
        body = read_document(data_dir, CATECHISM_FILE)
        (data_dir / CATECHISM_FILE).unlink()
        write_document(data_dir, "Tiny-Catechism.json", {**body, "slug": "Tiny-Catechism"})
        with pytest.raises(DoctrineDataError, match="'Tiny-Catechism'; expected lowercase"):
            load_doctrine_documents(data_dir)

    def test_rejects_duplicate_position(self, data_dir: Path) -> None:
        body = read_document(data_dir, CONFESSION_FILE)
        write_document(data_dir, CONFESSION_FILE, {**body, "position": 1})
        with pytest.raises(DoctrineDataError, match="tiny-catechism.json and tiny-confession.json"):
            load_doctrine_documents(data_dir)


class TestSchema:
    def test_rejects_empty_answer(self, data_dir: Path) -> None:
        body = read_document(data_dir, CATECHISM_FILE)
        _questions(body)[0]["answer"] = ""
        write_document(data_dir, CATECHISM_FILE, body)
        with pytest.raises(
            DoctrineDataError, match=r"tiny-catechism.json: does not match(.|\n)*answer"
        ):
            load_doctrine_documents(data_dir)

    def test_rejects_invalid_json(self, data_dir: Path) -> None:
        (data_dir / CATECHISM_FILE).write_text("{not json", encoding="utf-8")
        with pytest.raises(DoctrineDataError, match="tiny-catechism.json"):
            load_doctrine_documents(data_dir)
