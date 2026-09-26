"""The one structured log line each leader write produces.

Member data is sensitive (LGPD art. 11, constitution Security): the line carries the member
id, the editor id and how many fields changed — never names, dates, statuses or photo paths.
"""

import logging
from uuid import UUID

logger = logging.getLogger("features.members")


def log_member_write(
    event: str, member_id: int, editor_id: UUID | None, changed_fields: int
) -> None:
    """Log ``event`` for ``member_id`` with ids and a count only.

    >>> log_member_write("member_updated", 12, editor_id, changed_fields=2)
    """
    logger.info(
        event,
        extra={
            "member_id": member_id,
            "editor_id": str(editor_id) if editor_id else None,
            "changed_fields": changed_fields,
        },
    )
