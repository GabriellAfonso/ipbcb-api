from typing import Self

from pydantic import Field, model_validator

from core.application.dtos.strict_base import StrictBaseModel


Verse = str | list[str]


class BibleHeading(StrictBaseModel):
    """Section heading (pericope title) shown before a verse.

    Example: BibleHeading(verse=1, level=1, title="A criação do Universo")
    """

    verse: int = Field(ge=1)
    level: int = Field(ge=1, le=3)
    title: str = Field(min_length=1)


class BibleBook(StrictBaseModel):
    """Single book of a Bible version.

    Most verses are plain strings, but some NAA entries contain
    nested lists (multiple paragraphs within a single verse number).
    `headings` is parallel to `chapters`; empty when the version has none.
    """

    abbrev: str
    name: str
    chapters: list[list[Verse]]
    headings: list[list[BibleHeading]] = []

    @model_validator(mode="after")
    def _check_headings_fit_chapters(self) -> Self:
        if not self.headings:
            return self
        if len(self.headings) != len(self.chapters):
            raise ValueError(
                f"{self.abbrev}: headings has {len(self.headings)} chapters, "
                f"expected {len(self.chapters)} (one list per chapter)"
            )
        for number, (verses, headings) in enumerate(zip(self.chapters, self.headings), start=1):
            _check_heading_verses(self.abbrev, number, len(verses), headings)
        return self


def _check_heading_verses(
    abbrev: str, chapter: int, verse_count: int, headings: list[BibleHeading]
) -> None:
    for heading in headings:
        if heading.verse > verse_count:
            raise ValueError(
                f"{abbrev} {chapter}: heading {heading.title!r} points to verse "
                f"{heading.verse}, expected 1..{verse_count}"
            )
