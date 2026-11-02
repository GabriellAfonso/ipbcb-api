from django.db import models
from features.accounts.models.user import User
from features.accounts.validators import profile_photo_folder


def profile_photo_path(instance: "Profile", filename: str) -> str:
    """Build the storage path. ``filename`` already carries the validated extension.

    The folder is the username, or the user id for legacy usernames (see
    ``profile_photo_folder``).

    >>> profile_photo_path(profile, "6f1c2d....png")
    'profiles/ana.paula/6f1c2d....png'
    """
    folder = profile_photo_folder(instance.user.username, str(instance.user.pk))
    return f"profiles/{folder}/{filename}"


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    name = models.CharField(max_length=100, blank=True)
    photo = models.ImageField(upload_to=profile_photo_path, null=True, blank=True)
    # Gate on member content (renamed from is_member, specs/022-access-requests). The effective
    # access also counts the Admin and Liderança roles: core.domain.access.has_member_access.
    member_access = models.BooleanField(default=False)
    # Who set member_access from "Perfis" (approval or direct grant) and when; cleared on revoke.
    # Empty for flags set in the Django admin or before the record existed. SET_NULL: deleting the
    # leader's account keeps the grant.
    access_granted_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    access_granted_at = models.DateTimeField(null=True, blank=True)
    # Set by leaders in "Perfis": a blocked account cannot create access requests.
    access_requests_blocked = models.BooleanField(default=False)
    # The account's record on the church roll, for the app's "photos of me". Set by leaders only
    # (Django admin, or "Perfis" since spec 022) and nothing matches names automatically, since a
    # wrong link would show someone else's photos as "mine". One-to-one, so a member has at most
    # one profile; independent of member_access (specs/015-gallery-member-tags FR-001–FR-005).
    # Named, not imported, so accounts never imports the members feature.
    member = models.OneToOneField(
        "members.Member",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="profile",
    )
    # Where recovery codes go (specs/028-password-recovery). SECURITY: never a login, and never
    # read by Google sign-in, which finds accounts by User.email alone: this one is typed by the
    # user and unverified. Not unique, so typing someone's address cannot block its owner and
    # families can share one. Trimmed and lowercased by the DTOs.
    recovery_email = models.EmailField(blank=True, default="", db_index=True)
    # Optional, it only catches typos while signed in: recovery works unconfirmed, because the
    # code itself proves access to the mailbox.
    recovery_email_confirmed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self) -> str:
        return self.name

    @property
    def recovery_email_or_none(self) -> str | None:
        """The API's view of the address: ``null``, not ``""``, when there is none.

        >>> Profile().recovery_email_or_none
        """
        return self.recovery_email or None

    @property
    def recovery_email_confirmed(self) -> bool:
        """>>> Profile().recovery_email_confirmed
        False
        """
        return self.recovery_email_confirmed_at is not None
