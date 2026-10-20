"""Checks on the committed doctrine files that startup deliberately doesn't do (spec FR-013,
research R-03): per-document counts, the Confession 1.2 shape and the Bible references.

The files are produced outside the repository and reviewed by a person. A failure here is
reported to that person; it is never fixed by loosening a test."""

from collections.abc import Iterator

import pytest

from features.doctrine.dtos import (
    CatechismDocument,
    ConfessionDocument,
    ConfessionParagraph,
    DoctrineDocument,
    ProofText,
)
from features.doctrine.loading import DOCTRINE_DATA_DIR, load_doctrine_documents
from features.doctrine.tests.bible_verse_index import BIBLE_DATA_FILES, BibleVerseIndex

SHORTER = "westminster-shorter-catechism"
LARGER = "westminster-larger-catechism"
CONFESSION = "westminster-confession-of-faith"
EXPECTED_ITEM_COUNTS = {SHORTER: 107, LARGER: 196, CONFESSION: 33}

pytestmark = pytest.mark.skipif(
    not any(DOCTRINE_DATA_DIR.glob("*.json")),
    reason="features/doctrine/data has no .json yet; the reviewed files are added separately",
)


@pytest.fixture(scope="module")
def documents() -> dict[str, DoctrineDocument]:
    return {document.slug: document for document in load_doctrine_documents(DOCTRINE_DATA_DIR)}


@pytest.fixture(scope="module")
def verse_index() -> BibleVerseIndex:
    return BibleVerseIndex.from_files(BIBLE_DATA_FILES)


def _catechism(documents: dict[str, DoctrineDocument], slug: str) -> CatechismDocument:
    document = documents[slug]
    assert isinstance(document, CatechismDocument), f"{slug} must be a catechism"
    return document


def _confession(documents: dict[str, DoctrineDocument]) -> ConfessionDocument:
    document = documents[CONFESSION]
    assert isinstance(document, ConfessionDocument), f"{CONFESSION} must be a confession"
    return document


def _proof_texts(documents: dict[str, DoctrineDocument]) -> Iterator[tuple[str, ProofText]]:
    for slug in (SHORTER, LARGER):
        for question in _catechism(documents, slug).questions:
            yield from ((f"{slug} Q{question.number}", proof) for proof in question.proof_texts)


def _numbered_paragraphs(
    confession: ConfessionDocument,
) -> Iterator[tuple[str, ConfessionParagraph]]:
    for chapter in confession.chapters:
        yield from ((f"{chapter.number}.{p.number}", p) for p in chapter.paragraphs)


class TestDocumentSet:
    def test_exactly_the_three_documents_in_order(self) -> None:
        slugs = [document.slug for document in load_doctrine_documents(DOCTRINE_DATA_DIR)]
        assert slugs == [SHORTER, LARGER, CONFESSION]

    @pytest.mark.parametrize(("slug", "expected"), EXPECTED_ITEM_COUNTS.items())
    def test_item_counts(
        self, documents: dict[str, DoctrineDocument], slug: str, expected: int
    ) -> None:
        assert len(documents[slug].item_numbers()) == expected


class TestConfessionShape:
    def test_paragraph_1_2_has_two_lists_and_text_after(
        self, documents: dict[str, DoctrineDocument]
    ) -> None:
        paragraph = _confession(documents).chapters[0].paragraphs[1]
        assert paragraph.lists is not None and len(paragraph.lists) == 2
        assert paragraph.text_after is not None

    def test_no_other_paragraph_has_a_list(self, documents: dict[str, DoctrineDocument]) -> None:
        with_list = [
            label
            for label, paragraph in _numbered_paragraphs(_confession(documents))
            if label != "1.2" and (paragraph.lists or paragraph.text_after)
        ]
        assert with_list == []

    def test_no_proof_texts_in_the_confession(self) -> None:
        # The schema already forbids the key; this guards the raw file against a schema change.
        raw = (DOCTRINE_DATA_DIR / f"{CONFESSION}.json").read_text(encoding="utf-8")
        assert '"proof_texts"' not in raw


class TestBibleReferences:
    def test_every_book_is_a_bible_abbreviation(
        self, documents: dict[str, DoctrineDocument], verse_index: BibleVerseIndex
    ) -> None:
        offenders = [
            f"{label} '{proof.printed}': book {proof.reference.book!r}"
            for label, proof in _proof_texts(documents)
            if proof.reference and not verse_index.has_book(proof.reference.book)
        ]
        assert offenders == [], "Books that are not a Bible abbrev:\n" + "\n".join(offenders)

    def test_every_reference_exists_in_every_version(
        self, documents: dict[str, DoctrineDocument], verse_index: BibleVerseIndex
    ) -> None:
        offenders = [
            f"{label} '{proof.printed}': {reason}"
            for label, proof in _proof_texts(documents)
            if proof.reference and (reason := verse_index.missing_verses(proof.reference))
        ]
        assert offenders == [], "References that don't exist:\n" + "\n".join(offenders)
