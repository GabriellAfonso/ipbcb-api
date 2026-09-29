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
    is_member = models.BooleanField(default=False)
    # The account's record on the church roll, for the app's "photos of me". Set by hand in the
    # Django admin only: no endpoint writes it and nothing matches names automatically, since a
    # wrong link would show someone else's photos as "mine". One-to-one, so a member has at most
    # one profile; independent of is_member (specs/015-gallery-member-tags FR-001–FR-005). Named,
    # not imported, so accounts never imports the members feature.
    member = models.OneToOneField(
        "members.Member",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="profile",
    )

    def __str__(self) -> str:
        return self.name
