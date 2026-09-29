"""The change feed follows renames and deletions of tagged members.

A photo's ``members`` shows each member's name, so renaming or deleting a tagged member changes
the photo resource without touching the photo row (specs/015-gallery-member-tags FR-026). Every
path that does it — the members management API, the Django admin form, its bulk delete action,
a shell — saves or deletes a ``Member`` through the ORM, so model signals are the one hook they
share. The sender is named, never imported: the gallery does not import the members feature.

The members spec's "No signals" rule is about its change history, which needs the editor a
signal cannot know; these handlers need no editor (research R-07, decided with the requester).
Both run inside the caller's transaction, before the write; if a non-atomic caller's write then
fails, the photos are only reported once more, which the feed's client already tolerates.
"""

from typing import Any

from dependency_injector.wiring import Provide, inject
from django.db.models.signals import pre_delete, pre_save

from config.di import Container
from features.gallery.repositories.interfaces import PhotoTagRepository

_MEMBER_MODEL = "members.Member"


@inject
def _tag_repository(
    repository: PhotoTagRepository = Provide[Container.photo_tag_repository],
) -> PhotoTagRepository:
    # Module level so the container wires it (signals connect before any view is built).
    return repository


def mark_photos_of_renamed_member(
    sender: type[Any], instance: Any, raw: bool = False, **kwargs: Any
) -> None:
    """``pre_save`` on ``Member``: a changed name marks the member's live photos as changed.

    >>> mark_photos_of_renamed_member(Member, member)  # member.name was edited
    """
    update_fields = kwargs.get("update_fields")
    if raw or instance.pk is None:
        return  # fixtures load raw rows; a new member is tagged nowhere yet
    if update_fields is not None and "name" not in update_fields:
        return
    _tag_repository().touch_photos_if_renamed(instance.pk, instance.name)


def mark_photos_of_deleted_member(sender: type[Any], instance: Any, **kwargs: Any) -> None:
    """``pre_delete`` on ``Member``: its live photos change, since its tags go with it. Runs
    before the cascade removes the tags, while they can still be found.

    >>> mark_photos_of_deleted_member(Member, member)
    """
    _tag_repository().touch_photos_of_member(instance.pk)


def connect_member_signals() -> None:
    """Connect both handlers to ``members.Member`` by name. Idempotent (``dispatch_uid``).

    >>> connect_member_signals()  # from GalleryConfig.ready()
    """
    pre_save.connect(
        mark_photos_of_renamed_member,
        sender=_MEMBER_MODEL,
        dispatch_uid="gallery_member_renamed",
    )
    pre_delete.connect(
        mark_photos_of_deleted_member,
        sender=_MEMBER_MODEL,
        dispatch_uid="gallery_member_deleted",
    )
