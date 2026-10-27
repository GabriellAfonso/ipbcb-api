"""Sunday school domain exceptions (specs/026-sunday-school).

Their own module, like ``bible_exceptions``, to keep ``core/domain/exceptions.py`` under 500
lines; that module re-exports every name here. Messages are in Portuguese: the app shows them in
the panel editor.
"""

from collections.abc import Collection, Sequence

from core.domain.base_exceptions import NotFoundError, ValidationError

# Enough to point at every field of a typical mistake without flooding the editor.
MAX_LISTED_CONTENT_ERRORS = 10


class SundaySchoolYearNotFoundError(NotFoundError):
    """No year row, or (publicly) a year without a published lesson.

    >>> raise SundaySchoolYearNotFoundError(2031)
    """

    error_code: str = "SUNDAY_SCHOOL_YEAR_NOT_FOUND"

    def __init__(self, year: int) -> None:
        super().__init__(f"Ano da Escola Bíblica não encontrado: {year}.")
        self.year = year

    def extra_context(self) -> dict[str, object]:
        return {"year": self.year}


class SundaySchoolLessonNotFoundError(NotFoundError):
    """No lesson with this id, or a draft asked for publicly.

    >>> raise SundaySchoolLessonNotFoundError(42)
    """

    error_code: str = "SUNDAY_SCHOOL_LESSON_NOT_FOUND"

    def __init__(self, lesson_id: int) -> None:
        super().__init__(f"Aula não encontrada: id={lesson_id}.")
        self.lesson_id = lesson_id

    def extra_context(self) -> dict[str, object]:
        return {"lesson_id": self.lesson_id}


class SundaySchoolContentInvalidError(ValidationError):
    """The lesson content breaks the schema, or names an unknown icon or Bible passage. Each
    problem is a ``(path, message)`` pair, the path in dotted form
    (``sections.2.blocks.0.text``) so the app can show it next to the field.

    >>> raise SundaySchoolContentInvalidError([("sections.0.icon", "ícone desconhecido 'x'")])
    """

    error_code: str = "SUNDAY_SCHOOL_CONTENT_INVALID"

    def __init__(self, problems: Sequence[tuple[str, str]]) -> None:
        listed = problems[:MAX_LISTED_CONTENT_ERRORS]
        lines = "; ".join(f"{path}: {message}" for path, message in listed)
        more = len(problems) - len(listed)
        suffix = f" (e mais {more})" if more > 0 else ""
        super().__init__(f"Conteúdo da aula inválido — {lines}{suffix}.")
        self.problems = list(listed)

    def extra_context(self) -> dict[str, object]:
        return {"errors": [{"path": path, "message": message} for path, message in self.problems]}


class SundaySchoolOrderMismatchError(ValidationError):
    """The order sent for a year is not exactly that year's lessons, each once.

    >>> raise SundaySchoolOrderMismatchError(2026, [3, 7], [7, 7])
    """

    error_code: str = "SUNDAY_SCHOOL_ORDER_MISMATCH"

    def __init__(self, year: int, expected: Collection[int], received: Collection[int]) -> None:
        super().__init__(
            f"A ordem de {year} deve ter exatamente as aulas {sorted(expected)}, "
            f"cada uma uma vez; recebido {list(received)}."
        )
        self.expected = sorted(expected)

    def extra_context(self) -> dict[str, object]:
        return {"expected_lesson_ids": self.expected}
