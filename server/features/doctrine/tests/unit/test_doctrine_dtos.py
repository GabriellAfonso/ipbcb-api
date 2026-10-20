import pytest
from pydantic import TypeAdapter, ValidationError

from features.doctrine.dtos import (
    BibleReference,
    CatechismDocument,
    CatechismQuestion,
    ConfessionDocument,
    ConfessionParagraph,
    DoctrineDocument,
    ParagraphList,
    ProofText,
    VerseSpan,
)

DOCUMENT_ADAPTER: TypeAdapter[DoctrineDocument] = TypeAdapter(DoctrineDocument)


def _catechism_body() -> dict[str, object]:
    return {
        "slug": "tiny",
        "title": "Catecismo",
        "kind": "catechism",
        "position": 1,
        "questions": [{"number": 1, "question": "P?", "answer": "R.", "proof_texts": []}],
    }


def _confession_body() -> dict[str, object]:
    paragraph = {"number": 1, "text": "Texto."}
    chapter = {"number": 1, "title": "Título", "paragraphs": [paragraph]}
    return {
        "slug": "tiny",
        "title": "Confissão",
        "kind": "confession",
        "position": 1,
        "chapters": [chapter],
    }


class TestVerseSpan:
    def test_single_verse_is_valid(self) -> None:
        assert VerseSpan(start=27, end=27).end == 27

    @pytest.mark.parametrize(("start", "end"), [(5, 4), (0, 1)])
    def test_rejects_unordered_or_zero(self, start: int, end: int) -> None:
        with pytest.raises(ValidationError, match=f"start={start}, end={end}"):
            VerseSpan(start=start, end=end)


class TestBibleReference:
    def test_empty_verses_means_whole_chapter(self) -> None:
        assert BibleReference(book="Sl", chapter=23, verses=[]).verses == []

    def test_rejects_chapter_zero(self) -> None:
        with pytest.raises(ValidationError):
            BibleReference(book="Sl", chapter=0, verses=[])


class TestNonBlankText:
    @pytest.mark.parametrize("blank", ["", "   ", "\n"])
    def test_rejects_blank_answer(self, blank: str) -> None:
        with pytest.raises(ValidationError, match="non-whitespace"):
            CatechismQuestion(number=1, question="P?", answer=blank, proof_texts=[])

    @pytest.mark.parametrize("blank", ["", " "])
    def test_rejects_blank_printed_reference(self, blank: str) -> None:
        with pytest.raises(ValidationError):
            ProofText(printed=blank, reference=None)

    def test_rejects_blank_list_item(self) -> None:
        with pytest.raises(ValidationError):
            ParagraphList(heading="O Velho Testamento", items=["Gênesis", " "])

    def test_keeps_text_as_published(self) -> None:
        paragraph = ConfessionParagraph(number=1, text="  Texto com espaço. ")
        assert paragraph.text == "  Texto com espaço. "


class TestParagraphShape:
    def test_rejects_empty_lists(self) -> None:
        with pytest.raises(ValidationError):
            ConfessionParagraph(number=2, text="Livros:", lists=[])

    def test_rejects_list_without_items(self) -> None:
        with pytest.raises(ValidationError):
            ParagraphList(heading="O Novo Testamento", items=[])

    def test_plain_paragraph_dumps_only_number_and_text(self) -> None:
        dumped = ConfessionParagraph(number=1, text="Texto.").model_dump(exclude_unset=True)
        assert dumped == {"number": 1, "text": "Texto."}

    def test_explicit_null_reference_survives_the_dump(self) -> None:
        dumped = ProofText(printed="Sl 86-8", reference=None).model_dump(exclude_unset=True)
        assert dumped == {"printed": "Sl 86-8", "reference": None}


class TestDocumentKind:
    def test_catechism_kind_routes_to_catechism(self) -> None:
        document = DOCUMENT_ADAPTER.validate_python(_catechism_body())
        assert isinstance(document, CatechismDocument)
        assert document.item_numbers() == [1]

    def test_confession_kind_routes_to_confession(self) -> None:
        document = DOCUMENT_ADAPTER.validate_python(_confession_body())
        assert isinstance(document, ConfessionDocument)
        assert document.item_numbers() == [1]

    def test_rejects_unknown_key(self) -> None:
        body = {**_catechism_body(), "author": "Westminster"}
        with pytest.raises(ValidationError, match="extra_forbidden"):
            DOCUMENT_ADAPTER.validate_python(body)

    def test_rejects_unknown_kind(self) -> None:
        with pytest.raises(ValidationError):
            DOCUMENT_ADAPTER.validate_python({**_catechism_body(), "kind": "creed"})
