from core.domain.exceptions import BibleVersionNotFound
from features.bible.dtos import BibleBook
from features.bible.repositories.bible_text import BibleRepository


class BibleService:
    """Application logic for Bible data access."""

    def __init__(self, bible_repository: BibleRepository) -> None:
        self._repo = bible_repository

    def list_versions(self) -> list[str]:
        return self._repo.list_versions()

    def get_version(self, name: str) -> list[BibleBook]:
        """Return Bible books for a version, or raise BibleVersionNotFound."""
        result = self._repo.get_version(name)
        if result is None:
            raise BibleVersionNotFound(name)
        return result
