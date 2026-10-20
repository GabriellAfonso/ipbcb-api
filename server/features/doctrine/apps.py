from pathlib import Path

from django.apps import AppConfig
from django.core.exceptions import ImproperlyConfigured


class DoctrineConfig(AppConfig):
    name = "features.doctrine"

    def ready(self) -> None:
        # Eager on purpose (specs/019-doctrine-documents research R-02): the DI Singleton loads
        # lazily, so a broken data file would only fail on the first request. Here it stops
        # `migrate`, which runs before gunicorn in compose.prod.yml, so nothing is ever served
        # from a partial set.
        validate_doctrine_data()


def validate_doctrine_data(data_dir: Path | None = None) -> None:
    """Load every doctrine data file and refuse to start when one breaks a rule.

    >>> validate_doctrine_data(Path("features/doctrine/data"))
    """
    # Imported here, not at module level: apps.py is imported while the registry is loading.
    from features.doctrine.loading import (
        DOCTRINE_DATA_DIR,
        DoctrineDataError,
        load_doctrine_documents,
    )

    try:
        load_doctrine_documents(data_dir or DOCTRINE_DATA_DIR)
    except DoctrineDataError as exc:
        raise ImproperlyConfigured(f"Invalid doctrine data: {exc}") from exc
