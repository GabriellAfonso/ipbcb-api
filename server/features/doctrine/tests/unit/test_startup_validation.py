import re
from pathlib import Path

import pytest
from django.core.exceptions import ImproperlyConfigured

from features.doctrine.apps import validate_doctrine_data
from features.doctrine.tests.fixture_dirs import copy_fixture_dir, read_document, write_document


def test_valid_data_passes(tmp_path: Path) -> None:
    validate_doctrine_data(copy_fixture_dir("valid", tmp_path))


def test_empty_data_dir_passes(tmp_path: Path) -> None:
    validate_doctrine_data(tmp_path)


def test_broken_numbering_refuses_to_start(tmp_path: Path) -> None:
    data_dir = copy_fixture_dir("valid", tmp_path)
    body = read_document(data_dir, "tiny-catechism.json")
    questions = body["questions"]
    assert isinstance(questions, list)
    questions[1]["number"] = 3
    write_document(data_dir, "tiny-catechism.json", body)
    expected = "tiny-catechism.json: questions[1].number is 3; expected 2"
    with pytest.raises(ImproperlyConfigured, match=re.escape(expected)):
        validate_doctrine_data(data_dir)
