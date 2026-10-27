"""Content schema, scripture index and content validation (specs/026-sunday-school FR-009–FR-016)."""

from typing import Any

import pytest

from core.domain.exceptions import SundaySchoolContentInvalidError
from features.sunday_school.content_validation import validate_content
from features.sunday_school.domain.icons import STANDARD_SECTION_ICONS, LessonIcon
from features.sunday_school.domain.scripture_index import BookFacts, VerseRange
from features.sunday_school.tests.fakes import SMALL_SCRIPTURE, proof, sample_content

EVERY_BLOCK: list[dict[str, Any]] = [
    {"type": "paragraph", "text": "Texto *itálico*", "proof_texts": [proof("Dn", 2, 44)]},
    {"type": "list", "style": "roman", "items": [{"text": "I. Exílio"}]},
    {"type": "key_verse", "label": "Soberania", "text": "Ele muda…", "proof": proof("Dn", 2, 21)},
    {"type": "cards", "items": [{"icon": "heart", "label": "1º", "title": "Leia Obadias"}]},
    {
        "type": "comparison",
        "items": [
            {"label": "Esperavam", "title": "um leão", "highlight": False},
            {"label": "Chegou", "title": "um cordeiro", "highlight": True},
        ],
    },
    {"type": "steps", "items": [{"title": "Promessa"}, {"title": "Cumprimento"}]},
    {"type": "table", "header": ["Ref.", "Tema"], "rows": [["Dn 2", ""]]},
    {"type": "stats", "items": [{"value": "33", "label": "anos de vida"}]},
    {"type": "timeline", "events": [{"when": "27 d.C.", "text": "Batismo"}]},
    {"type": "book_facts", "book": "Mc", "author": "João Marcos"},
]


def _validate(content: dict[str, object]) -> dict[str, object]:
    return validate_content(content, SMALL_SCRIPTURE).model_dump(mode="json")


def _problems(content: dict[str, object]) -> list[tuple[str, str]]:
    with pytest.raises(SundaySchoolContentInvalidError) as caught:
        validate_content(content, SMALL_SCRIPTURE)
    return caught.value.problems


def _with_block(block: dict[str, Any]) -> dict[str, object]:
    return {"sections": [{"title": "S", "blocks": [block]}]}


class TestSchema:
    def test_every_block_type_is_accepted_and_normalized(self) -> None:
        stored = _validate({"sections": [{"title": "S", "blocks": EVERY_BLOCK}]})

        blocks = stored["sections"][0]["blocks"]  # type: ignore[index]
        assert [b["type"] for b in blocks] == [b["type"] for b in EVERY_BLOCK]
        assert blocks[1]["items"][0]["proof_texts"] == []
        assert stored["sections"][0]["icon"] is None  # type: ignore[index]

    @pytest.mark.parametrize(
        "content",
        [
            {"sections": []},
            {"sections": [{"title": "S", "blocks": []}]},
            {"sections": [{"title": "  ", "blocks": [{"type": "paragraph", "text": "x"}]}]},
            _with_block({"type": "image", "url": "x"}),
            _with_block({"type": "paragraph", "text": "x", "html": "<b>"}),
            _with_block({"type": "comparison", "items": [EVERY_BLOCK[4]["items"][0]]}),
            _with_block({"type": "table", "header": ["a", "b"], "rows": [["só uma"]]}),
            _with_block({"type": "list", "style": "dash", "items": [{"text": "x"}]}),
            {"sections": [{"title": "S", "icon": "star", "blocks": [EVERY_BLOCK[0]]}]},
        ],
    )
    def test_invalid_documents_are_refused(self, content: dict[str, object]) -> None:
        assert _problems(content)

    def test_problem_names_the_path(self) -> None:
        problems = _problems(sample_content(text=""))

        assert problems[0][0] == "sections.0.blocks.0.paragraph.text"


class TestScripture:
    @pytest.mark.parametrize(
        ("reference", "fragment"),
        [
            (proof("Xy", 1, 1), "livro desconhecido"),
            (proof("Dn", 4, 1), "3 capítulos"),
            (proof("Dn", 2, 40, 50), "49 versículos"),
        ],
    )
    def test_unknown_passages_are_refused(
        self, reference: dict[str, object], fragment: str
    ) -> None:
        problems = _problems(sample_content(proof_texts=[reference]))

        assert problems[0][0] == "sections.0.blocks.0.proof_texts.0.reference"
        assert fragment in problems[0][1]

    def test_reference_null_and_whole_chapter_pass(self) -> None:
        whole = {"printed": "Dn 2", "reference": {"book": "Dn", "chapter": 2, "verses": []}}
        loose = {"printed": "cf. Daniel", "reference": None}

        assert _validate(sample_content(proof_texts=[whole, loose]))

    def test_book_facts_book_must_exist(self) -> None:
        problems = _problems(_with_block({"type": "book_facts", "book": "Xy"}))

        assert problems == [("sections.0.blocks.0.book", "livro desconhecido 'Xy'")]

    def test_book_facts_are_derived(self) -> None:
        assert SMALL_SCRIPTURE.book_facts("Mc") == BookFacts("Marcos", 3, 2, 73)
        assert SMALL_SCRIPTURE.book_facts("Xy") is None

    def test_missing_passage_none_when_it_exists(self) -> None:
        assert SMALL_SCRIPTURE.missing_passage("Dn", 2, [VerseRange(1, 49)]) is None


class TestIcons:
    def test_standard_sections_use_listed_icons(self) -> None:
        assert len(STANDARD_SECTION_ICONS) == 6
        assert set(STANDARD_SECTION_ICONS.values()) <= set(LessonIcon)


class TestError:
    def test_message_lists_at_most_ten_problems(self) -> None:
        error = SundaySchoolContentInvalidError([(f"p{i}", "m") for i in range(12)])

        assert "(e mais 2)" in str(error)
        assert len(error.extra_context()["errors"]) == 10  # type: ignore[arg-type]
