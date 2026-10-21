from uuid import UUID

from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken

from features.accounts.repositories.interfaces import RefreshTokenRepository


class RefreshTokenRepositoryImpl(RefreshTokenRepository):
    """Blacklists through SimpleJWT's own tables, the ones its refresh check reads."""

    def revoke_all(self, user_id: UUID) -> int:
        """Blacklist every live refresh token of ``user_id``.

        Needed beside ``CHECK_REVOKE_TOKEN``: that check runs only when an access token
        authenticates, and ``RefreshService`` rebuilds a pair from the user without reading the
        old token's password hash — so after a password change an old refresh token would still
        mint a working pair (specs/021-user-account research R-03).

        >>> repo.revoke_all(user.pk)
        2
        """
        pending = OutstandingToken.objects.filter(user_id=user_id, blacklistedtoken__isnull=True)
        created = BlacklistedToken.objects.bulk_create(
            [BlacklistedToken(token=token) for token in pending], ignore_conflicts=True
        )
        return len(created)
