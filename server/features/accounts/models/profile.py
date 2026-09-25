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
    is_admin = models.BooleanField(default=False)

    def __str__(self) -> str:
        return self.name
