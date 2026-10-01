from uuid import UUID

from django.apps import apps
from django.contrib.auth import get_user_model
from django.contrib.auth.base_user import AbstractBaseUser
from django.db.models import QuerySet

from core.domain.worship import worship_name_pattern

# Lookup strings, never imports: core must not import the members or accounts features. The path
# is User -> Profile (accounts) -> Member (members) -> ministries.
_MINISTRY_NAME_LOOKUP = "profile__member__ministries__name__iregex"


class WorshipMembershipRepositoryImpl:
    """Who belongs to the worship ministry, matched by name (specs/017-sunday-setlist-push R-03).

    Only active users: an inactive account cannot sign in, so it neither saves nor receives.
    ``Member.is_active`` is deliberately not filtered (plan OQ-1).
    """

    def is_worship_member(self, user_id: UUID) -> bool:
        """>>> WorshipMembershipRepositoryImpl().is_worship_member(leader.pk)
        True
        """
        return self._members().filter(pk=user_id).exists()

    def worship_member_user_ids(self) -> set[UUID]:
        """>>> WorshipMembershipRepositoryImpl().worship_member_user_ids()
        {UUID('...')}
        """
        return set(self._members().values_list("pk", flat=True).distinct())

    def worship_ministry_exists(self) -> bool:
        """Whether a ministry with the worship name exists at all — absent means it was renamed.

        >>> WorshipMembershipRepositoryImpl().worship_ministry_exists()
        True
        """
        ministry = apps.get_model("members", "Ministry")
        return bool(ministry.objects.filter(name__iregex=worship_name_pattern()).exists())

    def _members(self) -> QuerySet[AbstractBaseUser]:
        return (
            get_user_model()
            .objects.filter(is_active=True)
            .filter(**{_MINISTRY_NAME_LOOKUP: worship_name_pattern()})
        )
