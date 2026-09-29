"""Features never import each other (constitution): the gallery and accounts reach the members
feature only through a string foreign key, the ``MemberDirectory`` port wired in
``config/di.py`` and signals connected by model name (specs/015-gallery-member-tags R-03)."""

import re
from pathlib import Path

import pytest

FEATURES = Path(__file__).resolve().parents[3]
IMPORT_OF_MEMBERS = re.compile(r"^\s*(from|import)\s+features\.members\b", re.MULTILINE)


def _sources(feature: str) -> list[Path]:
    return [
        path
        for path in (FEATURES / feature).rglob("*.py")
        if "tests" not in path.relative_to(FEATURES).parts
    ]


@pytest.mark.parametrize("feature", ["gallery", "accounts"])
def test_feature_does_not_import_members(feature: str) -> None:
    offenders = [
        str(path.relative_to(FEATURES))
        for path in _sources(feature)
        if IMPORT_OF_MEMBERS.search(path.read_text(encoding="utf-8"))
    ]

    assert _sources(feature), f"no sources found under {FEATURES / feature}"
    assert offenders == []
