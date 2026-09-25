from typing import IO
from uuid import uuid4

from django.core.files import File

from features.accounts.models.profile import Profile
from features.accounts.models.user import User
from features.accounts.repositories.interfaces import ProfileRepository


class ProfileRepositoryImpl(ProfileRepository):
    """Implementação do ProfileRepository usando Django ORM."""

    def get_or_create(self, user: User) -> tuple[Profile, bool]:
        return Profile.objects.get_or_create(user=user)

    def save_photo(self, profile: Profile, extension: str, upload: IO[bytes]) -> None:
        """Stream the upload to storage under an unguessable name.

        Django writes it in chunks, never all at once. Access control is authenticated
        delivery: media is served only through the check in features.media, members only
        for profiles/ (specs/009-protected-media-access). The random component is defence in
        depth, not collision avoidance: if an nginx edit ever re-published MEDIA_ROOT, a
        deterministic "profile_picture.png" would again let anyone fetch any member's photo
        from a URL built out of their username.
        """
        profile.photo.save(f"{uuid4().hex}.{extension}", File(upload), save=True)

    def delete_photo(self, profile: Profile) -> None:
        if profile.photo:
            profile.photo.delete(save=False)
            profile.photo = None
            profile.save(update_fields=["photo"])

    def update(self, profile: Profile, **fields: object) -> Profile:
        for key, value in fields.items():
            setattr(profile, key, value)
        profile.save(update_fields=list(fields.keys()))
        return profile
