from datetime import date

from core.application.dtos.push_dtos import PushMessage
from core.domain.push import PushMessageType


def test_data_values_are_strings() -> None:
    message = PushMessage(type=PushMessageType.CONFIRM_PLAYS, date=date(2026, 10, 4))
    assert message.as_data() == {"type": "confirm_plays", "date": "2026-10-04"}


def test_wire_types() -> None:
    assert {t.value for t in PushMessageType} == {
        "setlist_saved",
        "confirm_plays",
        "access_request_created",
        "access_request_approved",
        "access_request_denied",
        "schedule_week",
        "schedule_eve",
        "schedule_published",
    }


def test_schedule_message_carries_slots_and_month() -> None:
    message = PushMessage(type=PushMessageType.SCHEDULE_PUBLISHED, month="2026-11", slots="[]")
    assert message.as_data() == {"type": "schedule_published", "slots": "[]", "month": "2026-11"}


def test_schedule_message_carries_gender_when_known() -> None:
    message = PushMessage(type=PushMessageType.SCHEDULE_EVE, slots="[]", gender="F")
    assert message.as_data() == {"type": "schedule_eve", "slots": "[]", "gender": "F"}


def test_request_message_carries_only_the_fields_set() -> None:
    message = PushMessage(
        type=PushMessageType.ACCESS_REQUEST_DENIED, request_id=41, request_type="access"
    )
    assert message.as_data() == {
        "type": "access_request_denied",
        "request_id": "41",
        "request_type": "access",
    }


def test_denial_reason_reaches_the_payload() -> None:
    message = PushMessage(
        type=PushMessageType.ACCESS_REQUEST_DENIED,
        request_id=41,
        request_type="access",
        reason="Procure o pastor.",
    )
    assert message.as_data()["reason"] == "Procure o pastor."
