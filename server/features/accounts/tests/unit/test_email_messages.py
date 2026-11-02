"""The text of the e-mails with codes (specs/028-password-recovery FR-011, FR-021)."""

from features.accounts.domain.email_messages import confirmation_message, recovery_message
from features.accounts.dtos import AccountCodeDTO

ADDRESS = "ana@example.com"


def test_recovery_message_shows_each_username_with_its_code() -> None:
    message = recovery_message(
        ADDRESS,
        [
            AccountCodeDTO(username="ana", code="123456"),
            AccountCodeDTO(username="joao", code="654321"),
        ],
    )

    assert message.to == ADDRESS
    assert "ana: 123456" in message.body
    assert "joao: 654321" in message.body
    assert "mais de uma conta" in message.body


def test_recovery_message_for_one_account_does_not_mention_several() -> None:
    message = recovery_message(ADDRESS, [AccountCodeDTO(username="ana", code="123456")])

    assert "ana: 123456" in message.body
    assert "mais de uma conta" not in message.body


def test_recovery_message_names_the_app_and_says_to_ignore() -> None:
    message = recovery_message(ADDRESS, [AccountCodeDTO(username="ana", code="123456")])

    assert "IPB Castelo Branco" in message.body
    assert "ignore esta mensagem" in message.body
    assert "15 minutos" in message.body


def test_confirmation_message_carries_the_code() -> None:
    message = confirmation_message(ADDRESS, "123456")

    assert message.to == ADDRESS
    assert "123456" in message.body
    assert "IPB Castelo Branco" in message.body
    assert "ignore esta mensagem" in message.body
