from enum import StrEnum


class LessonStatus(StrEnum):
    """A draft is visible only in the panel; a published lesson is public."""

    DRAFT = "draft"
    PUBLISHED = "published"
