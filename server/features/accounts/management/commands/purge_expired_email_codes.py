"""Delete expired e-mail codes and stale send ledgers.

Run daily by the ``ipbcb_token_flush`` loop in compose.prod.yml; idempotent, so a missed or doubled
run is harmless (specs/028-password-recovery FR-019).
"""

from typing import Any

from dependency_injector.wiring import Provide, inject
from django.core.management.base import BaseCommand

from config.di import Container
from features.accounts.services.email_code_purge_service import EmailCodePurgeService


@inject
def _purge(
    purge_service: EmailCodePurgeService = Provide[Container.email_code_purge_service],
) -> int:
    return purge_service.purge_expired()


class Command(BaseCommand):
    help = "Delete expired e-mail codes and send ledgers untouched for an hour."

    def handle(self, *args: Any, **options: Any) -> None:
        # Exit 0 always: the loop runs again tomorrow, and a failing exit would only make the
        # container restart policy fight the loop.
        self.stdout.write(f"purged {_purge()} e-mail code rows")
