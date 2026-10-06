"""Delete Sunday setlists past their use: confirmed ones after 30 days, unconfirmed after 90.

Run daily by the ``ipbcb_token_flush`` loop in compose.prod.yml; idempotent, so a missed or
doubled run is harmless (specs/017-sunday-setlist-push FR-028).
"""

from typing import Any

from dependency_injector.wiring import Provide, inject
from django.core.management.base import BaseCommand

from config.di import Container
from features.songs.services.setlist_purge_service import SetlistPurgeService


@inject
def _purge(
    purge_service: SetlistPurgeService = Provide[Container.setlist_purge_service],
) -> int:
    return purge_service.purge_expired()


class Command(BaseCommand):
    help = "Delete setlists confirmed more than 30 days ago or unconfirmed more than 90 days ago."

    def handle(self, *args: Any, **options: Any) -> None:
        # Exit 0 always: the loop runs again tomorrow, and a failing exit would only make the
        # container restart policy fight the loop.
        self.stdout.write(f"purged {_purge()} setlists")
