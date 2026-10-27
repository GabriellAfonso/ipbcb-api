"""The lesson content document (specs/026-sunday-school data-model, R-04).

Strict: unknown fields and block types are refused. Text fields accept ``**bold**`` and
``*italic*`` as their only markup; the server stores text as given and never parses it. Bible
references are checked against the Bible afterwards, in ``content_validation``.
"""

from typing import Annotated, Literal

from pydantic import AfterValidator, Field, model_validator

from core.application.dtos.strict_base import StrictBaseModel
from features.sunday_school.domain.icons import LessonIcon

MAX_TEXT_LENGTH = 5000
MAX_SECTIONS = 30
MAX_BLOCKS_PER_SECTION = 60
MAX_ITEMS = 50
MAX_PROOF_TEXTS = 40
MAX_TABLE_COLUMNS = 10
MAX_TABLE_ROWS = 100


def _require_non_blank(value: str) -> str:
    # Stored as written (inline emphasis included), so checked but never stripped.
    if not value.strip():
        raise ValueError(f"o texto não pode ficar em branco; recebido {value!r}")
    return value


Text = Annotated[str, Field(max_length=MAX_TEXT_LENGTH), AfterValidator(_require_non_blank)]
ShortText = Annotated[str, Field(max_length=200), AfterValidator(_require_non_blank)]


class VerseSpan(StrictBaseModel):
    """Inclusive verse range in one chapter; a single verse has ``start == end``.

    >>> VerseSpan(start=3, end=5)
    """

    start: int
    end: int

    @model_validator(mode="after")
    def _require_ordered(self) -> "VerseSpan":
        if not 1 <= self.start <= self.end:
            raise ValueError(
                f"intervalo de versículos deve ter 1 <= start <= end; "
                f"recebido start={self.start}, end={self.end}"
            )
        return self


class BibleReference(StrictBaseModel):
    """Same shape as doctrine proof texts: ``book`` is the Bible ``abbrev`` and an empty
    ``verses`` list is the whole chapter.

    >>> BibleReference(book="Dn", chapter=2, verses=[VerseSpan(start=44, end=44)])
    """

    book: Annotated[str, Field(min_length=1, max_length=8)]
    chapter: int = Field(ge=1)
    verses: list[VerseSpan] = Field(max_length=MAX_PROOF_TEXTS)


class ProofText(StrictBaseModel):
    """A passage as printed; ``reference`` is None when it cannot be pinned.

    >>> ProofText(printed="Dn 2.44", reference=None)
    """

    printed: ShortText
    reference: BibleReference | None


ProofTexts = Annotated[list[ProofText], Field(max_length=MAX_PROOF_TEXTS)]


class ParagraphBlock(StrictBaseModel):
    type: Literal["paragraph"]
    text: Text
    proof_texts: ProofTexts = []


class ListItem(StrictBaseModel):
    text: Text
    proof_texts: ProofTexts = []


class ListBlock(StrictBaseModel):
    type: Literal["list"]
    style: Literal["bullet", "numbered", "roman"]
    items: Annotated[list[ListItem], Field(min_length=1, max_length=MAX_ITEMS)]


class KeyVerseBlock(StrictBaseModel):
    type: Literal["key_verse"]
    label: ShortText | None = None
    text: Text
    proof: ProofText


class Card(StrictBaseModel):
    icon: LessonIcon | None = None
    label: ShortText | None = None
    title: ShortText
    text: Text | None = None
    proof_texts: ProofTexts = []


class CardsBlock(StrictBaseModel):
    type: Literal["cards"]
    items: Annotated[list[Card], Field(min_length=1, max_length=MAX_ITEMS)]


class ComparisonItem(StrictBaseModel):
    label: ShortText
    title: ShortText
    text: Text | None = None
    highlight: bool


class ComparisonBlock(StrictBaseModel):
    type: Literal["comparison"]
    items: Annotated[list[ComparisonItem], Field(min_length=2, max_length=2)]


class Step(StrictBaseModel):
    label: ShortText | None = None
    title: ShortText
    text: Text | None = None


class StepsBlock(StrictBaseModel):
    type: Literal["steps"]
    items: Annotated[list[Step], Field(min_length=1, max_length=MAX_ITEMS)]


TableCell = Annotated[str, Field(max_length=MAX_TEXT_LENGTH)]


class TableBlock(StrictBaseModel):
    type: Literal["table"]
    header: Annotated[list[ShortText], Field(min_length=1, max_length=MAX_TABLE_COLUMNS)]
    rows: Annotated[list[list[TableCell]], Field(min_length=1, max_length=MAX_TABLE_ROWS)]

    @model_validator(mode="after")
    def _require_rectangular(self) -> "TableBlock":
        width = len(self.header)
        for index, row in enumerate(self.rows):
            if len(row) != width:
                raise ValueError(
                    f"a linha {index} tem {len(row)} células; esperado {width}, como o cabeçalho"
                )
        return self


class Stat(StrictBaseModel):
    value: Annotated[str, Field(max_length=20), AfterValidator(_require_non_blank)]
    label: ShortText


class StatsBlock(StrictBaseModel):
    type: Literal["stats"]
    items: Annotated[list[Stat], Field(min_length=1, max_length=MAX_ITEMS)]


class TimelineEvent(StrictBaseModel):
    when: Annotated[str, Field(max_length=40), AfterValidator(_require_non_blank)]
    text: Text


class TimelineBlock(StrictBaseModel):
    type: Literal["timeline"]
    events: Annotated[list[TimelineEvent], Field(min_length=1, max_length=MAX_ITEMS)]


class BookFactsBlock(StrictBaseModel):
    """Chapter and verse counts and the book's number are derived from the Bible, never typed
    (spec FR-016): they come in the lesson response's ``books`` map."""

    type: Literal["book_facts"]
    book: Annotated[str, Field(min_length=1, max_length=8)]
    author: ShortText | None = None
    date: ShortText | None = None
    style: ShortText | None = None
    reading_time: ShortText | None = None


Block = Annotated[
    ParagraphBlock
    | ListBlock
    | KeyVerseBlock
    | CardsBlock
    | ComparisonBlock
    | StepsBlock
    | TableBlock
    | StatsBlock
    | TimelineBlock
    | BookFactsBlock,
    Field(discriminator="type"),
]


class Section(StrictBaseModel):
    title: ShortText
    icon: LessonIcon | None = None
    blocks: Annotated[list[Block], Field(min_length=1, max_length=MAX_BLOCKS_PER_SECTION)]


class LessonContent(StrictBaseModel):
    """A whole lesson body.

    >>> LessonContent.model_validate({"sections": [{"title": "Contexto", "blocks": [
    ...     {"type": "paragraph", "text": "O livro de **Daniel**..."}]}]})
    """

    sections: Annotated[list[Section], Field(min_length=1, max_length=MAX_SECTIONS)]
