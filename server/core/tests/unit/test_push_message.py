from datetime import date

from core.application.dtos.push_dtos import PushMessage
from core.domain.push import PushMessageType


def test_data_values_are_strings() -> None:
    message = PushMessage(type=PushMessageType.CONFIRM_PLAYS, date=date(2026, 10, 4))
    assert message.as_data() == {"type": "confirm_plays", "date": "2026-10-04"}


def test_wire_types() -> None:
    assert {t.value for t in PushMessageType} == {"setlist_saved", "confirm_plays"}
