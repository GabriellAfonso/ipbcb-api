from collections.abc import Collection, Iterable
from uuid import UUID

from core.models import DeviceToken


class DeviceTokenRepositoryImpl:
    """Device push tokens through the ORM (specs/017-sunday-setlist-push R-14)."""

    def register(self, user_id: UUID, token: str) -> None:
        """Store ``token`` for ``user_id``, moving it from any previous owner.

        >>> DeviceTokenRepositoryImpl().register(ana.pk, "fcm-token")
        """
        DeviceToken.objects.update_or_create(token=token, defaults={"user_id": user_id})

    def unregister(self, user_id: UUID, token: str) -> None:
        """Delete ``token`` only when ``user_id`` owns it; anything else changes nothing.

        >>> DeviceTokenRepositoryImpl().unregister(ana.pk, "fcm-token")
        """
        DeviceToken.objects.filter(token=token, user_id=user_id).delete()

    def tokens_for(self, user_ids: Collection[UUID]) -> list[str]:
        """Every token of every user in ``user_ids``, one query.

        >>> DeviceTokenRepositoryImpl().tokens_for({ana.pk})
        ['fcm-token']
        """
        if not user_ids:
            return []
        rows = DeviceToken.objects.filter(user_id__in=user_ids).values_list("token", flat=True)
        return list(rows)

    def delete_tokens(self, tokens: Iterable[str]) -> int:
        """Delete these tokens whoever owns them — FCM said they are dead. Returns how many.

        >>> DeviceTokenRepositoryImpl().delete_tokens(["fcm-token"])
        1
        """
        deleted, _ = DeviceToken.objects.filter(token__in=list(tokens)).delete()
        return deleted
