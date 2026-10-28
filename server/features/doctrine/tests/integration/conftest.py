from pathlib import Path

import pytest

from features.doctrine.loading import load_doctrine_documents
from features.doctrine.tests.fixture_dirs import copy_fixture_dir
from features.doctrine.tests.stored_documents import store_documents


class ServedFixtureDocuments:
    """The fixture documents the views are serving, stored in the table from a private copy of
    the fixture files a test may edit."""

    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir

    def reload(self) -> None:
        """Store ``data_dir`` again, as a correction migration would.

        >>> fixture_doctrine.reload()
        """
        store_documents(load_doctrine_documents(self.data_dir))


@pytest.fixture
def fixture_doctrine(db: None, tmp_path: Path) -> ServedFixtureDocuments:
    """Serve a private copy of ``fixtures/valid`` instead of the migrated documents."""
    served = ServedFixtureDocuments(copy_fixture_dir("valid", tmp_path))
    served.reload()
    return served
