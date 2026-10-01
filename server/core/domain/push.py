"""Push message kinds the server sends to the app (specs/017-sunday-setlist-push,
contracts/push-messages.md). No Django import here."""

from enum import StrEnum


class PushMessageType(StrEnum):
    """The value is the wire ``type`` the app switches on."""

    SETLIST_SAVED = "setlist_saved"
    CONFIRM_PLAYS = "confirm_plays"
