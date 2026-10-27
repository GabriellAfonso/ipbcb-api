"""Adds the Bible facts of the books a lesson's ``book_facts`` cards name (research R-03)."""

from features.sunday_school.content_schema import LessonContent
from features.sunday_school.content_validation import book_facts_books
from features.sunday_school.domain.scripture_index import ScriptureIndex
from features.sunday_school.dtos import BookFactsDTO, LessonDTO, LessonRecordDTO


def with_books(record: LessonRecordDTO, scripture: ScriptureIndex) -> LessonDTO:
    """The lesson as served: content untouched, ``books`` filled from the Bible.

    >>> with_books(record, scripture).books
    {'Mc': BookFactsDTO(name='Marcos', position=41, chapters=16, verses=678)}
    """
    content = LessonContent.model_validate(record.content)
    books: dict[str, BookFactsDTO] = {}
    for _, book in book_facts_books(content):
        facts = scripture.book_facts(book)
        if facts is not None:
            books[book] = BookFactsDTO(**facts._asdict())
    return LessonDTO(**record.model_dump(), books=books)
