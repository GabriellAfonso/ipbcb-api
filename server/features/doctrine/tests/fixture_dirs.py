"""Builds doctrine data directories for tests. Each test copies the valid fixtures into its own
``tmp_path`` and breaks one rule there, so no broken file is ever committed."""

import json
import shutil
from pathlib import Path

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def copy_fixture_dir(name: str, tmp_path: Path) -> Path:
    """Copy ``fixtures/<name>/`` into ``tmp_path`` and return the copy.

    >>> copy_fixture_dir("valid", tmp_path)
    PosixPath('/tmp/.../valid')
    """
    target = tmp_path / name
    shutil.copytree(FIXTURES_DIR / name, target)
    return target


def read_document(data_dir: Path, file_name: str) -> dict[str, object]:
    """Parse one data file as a plain JSON object, to edit it in a test.

    >>> read_document(data_dir, "tiny-catechism.json")["slug"]
    'tiny-catechism'
    """
    loaded: dict[str, object] = json.loads((data_dir / file_name).read_text(encoding="utf-8"))
    return loaded


def write_document(data_dir: Path, file_name: str, body: dict[str, object]) -> Path:
    """Write ``body`` as ``data_dir/file_name`` (UTF-8) and return the path.

    >>> write_document(data_dir, "tiny-catechism.json", {"slug": "tiny-catechism", ...})
    """
    path = data_dir / file_name
    path.write_text(json.dumps(body, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
