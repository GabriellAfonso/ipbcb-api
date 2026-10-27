"""Turns a raw content document into a validated ``LessonContent``, or one domain error listing
every problem by path (specs/026-sunday-school R-05).

Two passes: the schema, then the Bible — every non-null reference must exist in every
translation and every ``book_facts.book`` must be a Bible book.
"""

from collections.abc import Iterator, Mapping

from pydantic import ValidationError as PydanticValidationError

from core.domain.exceptions import SundaySchoolContentInvalidError
from features.sunday_school.content_schema import (
    BookFactsBlock,
    CardsBlock,
    KeyVerseBlock,
    LessonContent,
    ListBlock,
    ParagraphBlock,
    ProofText,
)
from features.sunday_school.domain.scripture_index import ScriptureIndex, VerseRange

Problem = tuple[str, str]


def validate_content(raw: Mapping[str, object], scripture: ScriptureIndex) -> LessonContent:
    """The content as stored, or ``SundaySchoolContentInvalidError``.

    >>> validate_content({"sections": []}, scripture)
    Traceback (most recent call last):
    SundaySchoolContentInvalidError: Conteúdo da aula inválido — sections: ...
    """
    try:
        content = LessonContent.model_validate(raw)
    except PydanticValidationError as exc:
        raise SundaySchoolContentInvalidError(schema_problems(exc)) from exc
    problems = scripture_problems(content, scripture)
    if problems:
        raise SundaySchoolContentInvalidError(problems)
    return content


def schema_problems(exc: PydanticValidationError) -> list[Problem]:
    """Each Pydantic error as ``(dotted path, message)``. The discriminator tag Pydantic adds to
    the path (``sections.0.blocks.1.paragraph.text``) is kept: it names the block type."""
    return [(".".join(str(part) for part in err["loc"]), err["msg"]) for err in exc.errors()]


def scripture_problems(content: LessonContent, scripture: ScriptureIndex) -> list[Problem]:
    problems: list[Problem] = []
    for path, proof in proof_texts(content):
        reason = _reference_problem(proof, scripture)
        if reason is not None:
            problems.append((f"{path}.reference", f"{proof.printed!r}: {reason}"))
    for path, book in book_facts_books(content):
        if not scripture.has_book(book):
            problems.append((f"{path}.book", f"livro desconhecido {book!r}"))
    return problems


def _reference_problem(proof: ProofText, scripture: ScriptureIndex) -> str | None:
    reference = proof.reference
    if reference is None:
        return None
    spans = [VerseRange(span.start, span.end) for span in reference.verses]
    return scripture.missing_passage(reference.book, reference.chapter, spans)


def proof_texts(content: LessonContent) -> Iterator[tuple[str, ProofText]]:
    """Every Bible reference in the document with its path.

    >>> [path for path, _ in proof_texts(content)]
    ['sections.0.blocks.2.proof', 'sections.1.blocks.0.items.3.proof_texts.0']
    """
    for s, section in enumerate(content.sections):
        for b, block in enumerate(section.blocks):
            yield from _block_proof_texts(f"sections.{s}.blocks.{b}", block)


def _block_proof_texts(path: str, block: object) -> Iterator[tuple[str, ProofText]]:
    if isinstance(block, KeyVerseBlock):
        yield f"{path}.proof", block.proof
    if isinstance(block, ParagraphBlock):
        yield from _numbered(f"{path}.proof_texts", block.proof_texts)
    if isinstance(block, ListBlock):
        for i, item in enumerate(block.items):
            yield from _numbered(f"{path}.items.{i}.proof_texts", item.proof_texts)
    if isinstance(block, CardsBlock):
        for i, card in enumerate(block.items):
            yield from _numbered(f"{path}.items.{i}.proof_texts", card.proof_texts)


def _numbered(path: str, proofs: list[ProofText]) -> Iterator[tuple[str, ProofText]]:
    for index, proof in enumerate(proofs):
        yield f"{path}.{index}", proof


def book_facts_books(content: LessonContent) -> Iterator[tuple[str, str]]:
    """Every ``book_facts`` block's book with the block's path."""
    for s, section in enumerate(content.sections):
        for b, block in enumerate(section.blocks):
            if isinstance(block, BookFactsBlock):
                yield f"sections.{s}.blocks.{b}", block.book
