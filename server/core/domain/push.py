"""Push message kinds the server sends to the app (specs/017-sunday-setlist-push,
contracts/push-messages.md; specs/022-access-requests). No Django import here."""

from enum import StrEnum


class PushMessageType(StrEnum):
    """The value is the wire ``type`` the app switches on."""

    SETLIST_SAVED = "setlist_saved"
    CONFIRM_PLAYS = "confirm_plays"
    # Access requests (specs/022-access-requests contracts/access-api.md).
    ACCESS_REQUEST_CREATED = "access_request_created"
    ACCESS_REQUEST_APPROVED = "access_request_approved"
    ACCESS_REQUEST_DENIED = "access_request_denied"
