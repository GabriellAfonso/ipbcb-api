import re

import pytest

from core.domain.worship import WORSHIP_MINISTRY_NAME, worship_name_pattern


def _matches(name: str) -> bool:
    return re.match(worship_name_pattern(), name, flags=re.IGNORECASE) is not None


@pytest.mark.parametrize("name", ["Louvor", "louvor", "LOUVOR", "  Louvor ", "\tlouvor\n"])
def test_name_variants_match(name: str) -> None:
    assert _matches(name)


@pytest.mark.parametrize("name", ["Louvor e Artes", "Ministério de Louvor", "Louv", ""])
def test_other_names_do_not_match(name: str) -> None:
    assert not _matches(name)


def test_constant_is_the_portuguese_name() -> None:
    assert WORSHIP_MINISTRY_NAME == "Louvor"
