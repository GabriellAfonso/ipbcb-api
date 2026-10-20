from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from dependency_injector import providers

from features.doctrine.repositories import DoctrineRepositoryImpl
from features.doctrine.tests.fixture_dirs import copy_fixture_dir

if TYPE_CHECKING:
    from config.di import Container


class ServedFixtureDocuments:
    """The fixture documents the views are serving, from a private copy a test may edit.

    The override holds one ``providers.Object``; ``reload`` swaps what it provides instead of
    stacking a second override, which would outlive the fixture's ``with`` block."""

    def __init__(self, data_dir: Path, holder: providers.Object[DoctrineRepositoryImpl]) -> None:
        self.data_dir = data_dir
        self._holder = holder

    def reload(self) -> None:
        """Re-read ``data_dir``, as a restart after a deploy would.

        >>> fixture_doctrine.reload()
        """
        self._holder.set_provides(DoctrineRepositoryImpl(self.data_dir))


@pytest.fixture
def fixture_doctrine(di_container: "Container", tmp_path: Path) -> Iterator[ServedFixtureDocuments]:
    """Serve a private copy of ``fixtures/valid`` instead of the committed data."""
    data_dir = copy_fixture_dir("valid", tmp_path)
    holder = providers.Object(DoctrineRepositoryImpl(data_dir))
    with di_container.doctrine_repository.override(holder):
        yield ServedFixtureDocuments(data_dir, holder)
