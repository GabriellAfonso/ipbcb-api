from typing import Annotated, Literal

from pydantic import AfterValidator, Field, model_validator

from core.application.dtos.strict_base import StrictBaseModel


def _require_non_blank(value: str) -> str:
    # Text is stored as published (spec FR-005), so it is checked but never stripped.
    if not value.strip():
        raise ValueError(f"text must contain a non-whitespace character; got {value!r}")
    return value


_NonBlankText = Annotated[str, AfterValidator(_require_non_blank)]


class VerseSpan(StrictBaseModel):
    """Inclusive verse range inside one chapter; a single verse has ``start == end``.

    >>> VerseSpan(start=27, end=27)
    """

    start: int
    end: int

    @model_validator(mode="after")
    def _require_ordered(self) -> "VerseSpan":
        if not 1 <= self.start <= self.end:
            raise ValueError(
                f"verse span must satisfy 1 <= start <= end; got start={self.start}, end={self.end}"
            )
        return self


class BibleReference(StrictBaseModel):
    """Bible location a proof text points to. ``book`` is the Bible domain's ``abbrev``
    (e.g. "1Tn"), and an empty ``verses`` list means the whole chapter.

    >>> BibleReference(book="Lc", chapter=24, verses=[VerseSpan(start=27, end=27)])
    """

    book: _NonBlankText
    chapter: int = Field(ge=1)
    verses: list[VerseSpan]


class ProofText(StrictBaseModel):
    """One proof-text segment exactly as printed; ``reference`` is ``None`` when the
    printed text could not be interpreted with certainty (spec FR-009, FR-010).

    >>> ProofText(printed="Sl 86-8", reference=None)
    """

    printed: _NonBlankText
    reference: BibleReference | None


class CatechismQuestion(StrictBaseModel):
    number: int
    question: _NonBlankText
    answer: _NonBlankText
    proof_texts: list[ProofText]


class ParagraphList(StrictBaseModel):
    """Titled list inside a paragraph, e.g. the Old Testament books of Confession 1.2."""

    heading: _NonBlankText
    items: Annotated[list[_NonBlankText], Field(min_length=1)]


class ConfessionParagraph(StrictBaseModel):
    """Numbered paragraph. ``lists`` and ``text_after`` exist only where the published text
    has a list (Confession 1.2); every other paragraph has just ``text``.

    >>> ConfessionParagraph(number=1, text="Ainda que a luz da natureza...")
    """

    number: int
    text: _NonBlankText
    lists: Annotated[list[ParagraphList], Field(min_length=1)] | None = None
    text_after: _NonBlankText | None = None


class ConfessionChapter(StrictBaseModel):
    number: int
    title: _NonBlankText
    paragraphs: list[ConfessionParagraph]


class CatechismDocument(StrictBaseModel):
    """Question-and-answer document (Shorter and Larger Catechisms)."""

    slug: str
    title: _NonBlankText
    kind: Literal["catechism"]
    position: int
    questions: list[CatechismQuestion]

    def item_numbers(self) -> list[int]:
        """Numbers of the top-level items, in file order.

        >>> document.item_numbers()
        [1, 2, 3]
        """
        return [question.number for question in self.questions]


class ConfessionDocument(StrictBaseModel):
    """Chapter-and-paragraph document (Confession of Faith)."""

    slug: str
    title: _NonBlankText
    kind: Literal["confession"]
    position: int
    chapters: list[ConfessionChapter]

    def item_numbers(self) -> list[int]:
        """Numbers of the top-level items, in file order.

        >>> document.item_numbers()
        [1, 2, 3]
        """
        return [chapter.number for chapter in self.chapters]


DoctrineDocument = Annotated[CatechismDocument | ConfessionDocument, Field(discriminator="kind")]


class DoctrineDocumentSummary(StrictBaseModel):
    """List entry for the Doctrine screen; ``item_count`` is questions or chapters."""

    slug: str
    title: str
    kind: Literal["catechism", "confession"]
    item_count: int
