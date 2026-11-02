"""The text of the e-mails with codes (specs/028-password-recovery FR-021). User-facing, so
Portuguese: plain and short, naming the app and saying what to do if nobody asked."""

from collections.abc import Sequence
from typing import Final

from features.accounts.domain.email_codes import CODE_LIFETIME
from features.accounts.dtos import AccountCodeDTO, EmailMessageDTO

_APP_NAME: Final = "IPB Castelo Branco"
_LIFETIME_MINUTES: Final = int(CODE_LIFETIME.total_seconds() // 60)
_FOOTER: Final = (
    f"O código vale por {_LIFETIME_MINUTES} minutos e só pode ser usado uma vez.\n\n"
    "Se você não pediu isso, ignore esta mensagem."
)


def recovery_message(address: str, account_codes: Sequence[AccountCodeDTO]) -> EmailMessageDTO:
    """One message per address, with the username and code of each account: people forget
    usernames, and a family may share an address.

    >>> recovery_message("ana@example.com", [AccountCodeDTO(username="ana", code="123456")]).to
    'ana@example.com'
    """
    lines = "\n".join(f"{account.username}: {account.code}" for account in account_codes)
    intro = (
        "Use o código abaixo para criar uma nova senha."
        if len(account_codes) == 1
        else "Este e-mail está em mais de uma conta. Use o código da conta que quer recuperar."
    )
    return EmailMessageDTO(
        to=address,
        subject=f"Recuperação de senha - {_APP_NAME}",
        body=f"Recebemos um pedido de recuperação de senha no app {_APP_NAME}.\n\n"
        f"{intro}\n\n{lines}\n\n{_FOOTER}",
    )


def confirmation_message(address: str, code: str) -> EmailMessageDTO:
    """>>> confirmation_message("ana@example.com", "123456").to
    'ana@example.com'
    """
    return EmailMessageDTO(
        to=address,
        subject=f"Confirmação de e-mail - {_APP_NAME}",
        body=f"Use o código abaixo para confirmar este e-mail no app {_APP_NAME}.\n\n"
        f"{code}\n\n{_FOOTER}",
    )
