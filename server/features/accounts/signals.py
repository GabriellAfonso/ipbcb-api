import os
from typing import Any

from django.db.models.signals import post_save, pre_save, post_delete
from django.dispatch import receiver

from features.accounts.models.user import User
from features.accounts.models.profile import Profile


@receiver(post_save, sender=User)
def create_user_profile(sender: type[User], instance: User, created: bool, **kwargs: Any) -> None:
    if created:
        Profile.objects.create(
            user=instance, name=f"{instance.first_name} {instance.last_name}".strip().title()
        )


@receiver(post_save, sender=User)
def save_user_profile(sender: type[User], instance: User, **kwargs: Any) -> None:
    if hasattr(instance, "profile"):
        instance.profile.save()


@receiver(pre_save, sender=Profile)
def delete_old_photo_on_change(sender: type[Profile], instance: Profile, **kwargs: Any) -> None:
    if not instance.pk:
        return

    try:
        old_photo = Profile.objects.get(pk=instance.pk).photo
    except Profile.DoesNotExist:
        return

    new_photo = instance.photo
    if old_photo and old_photo != new_photo:
        if os.path.isfile(old_photo.path):
            os.remove(old_photo.path)


@receiver(post_delete, sender=Profile)
def delete_photo_on_profile_delete(sender: type[Profile], instance: Profile, **kwargs: Any) -> None:
    if instance.photo and os.path.isfile(instance.photo.path):
        os.remove(instance.photo.path)
