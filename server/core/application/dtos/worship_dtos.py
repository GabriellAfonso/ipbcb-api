from pydantic import ConfigDict

from core.application.dtos.strict_base import StrictBaseModel


class WorshipFlagsDTO(StrictBaseModel):
    """What the app needs to decide which worship screens and actions to show.

    >>> WorshipFlagsDTO(is_worship_member=True, can_save_setlist=False)
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    is_worship_member: bool
    can_save_setlist: bool
