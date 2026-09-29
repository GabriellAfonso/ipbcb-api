from core.application.dtos.strict_base import StrictBaseModel


class MemberRef(StrictBaseModel):
    """A member as the gallery shows it: id and display name, nothing else of the roll
    (specs/015-gallery-member-tags FR-035)."""

    id: int
    name: str


class TaggedMember(StrictBaseModel):
    """A member tagged in at least one live photo, with how many."""

    id: int
    name: str
    photo_count: int


class PhotoMembersReplace(StrictBaseModel):
    """The full new set of members tagged in one photo; ``[]`` clears it."""

    member_ids: list[int]


class PhotoTagsBulkChange(StrictBaseModel):
    """Pairs to add and remove over many photos; every other tag of those photos stays."""

    photo_ids: list[int]
    add_member_ids: list[int] = []
    remove_member_ids: list[int] = []
