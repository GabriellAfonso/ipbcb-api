"""Icon names a lesson may use (specs/026-sunday-school R-06).

A closed list owned by this project: the app draws each one with the Phosphor icon of the same
name in kebab case (``hands_praying`` → ``HandsPraying``), duotone. Adding a name means changing
server and app together.
"""

from collections.abc import Mapping
from enum import StrEnum
from types import MappingProxyType


class LessonIcon(StrEnum):
    HEART = "heart"
    SCALES = "scales"
    SHIELD = "shield"
    PLANT = "plant"
    HANDS_PRAYING = "hands_praying"
    CROWN = "crown"
    CROSS = "cross"
    BOOK_OPEN = "book_open"
    SCROLL = "scroll"
    FLAME = "flame"
    BIRD = "bird"
    CHURCH = "church"
    HOURGLASS = "hourglass"
    SWORD = "sword"
    MOUNTAINS = "mountains"
    LIGHTNING = "lightning"


# The six sections every lesson follows, with the icon the import and the app's new-lesson
# template give them. The server applies no default on write: this table is the shared record.
STANDARD_SECTION_ICONS: Mapping[str, LessonIcon] = MappingProxyType(
    {
        "Contexto no Drama das Escrituras": LessonIcon.HOURGLASS,
        "Objetivo teológico": LessonIcon.CROWN,
        "Estrutura / Esboço": LessonIcon.BOOK_OPEN,
        "Verdades teológicas": LessonIcon.SHIELD,
        "Versículos-chave": LessonIcon.SCROLL,
        "Exortação devocional": LessonIcon.HANDS_PRAYING,
    }
)
