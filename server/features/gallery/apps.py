from django.apps import AppConfig


class GalleryConfig(AppConfig):
    name = "features.gallery"

    def ready(self) -> None:
        # Renames and deletions of tagged members reach the change feed through these
        # (specs/015-gallery-member-tags research R-07).
        from features.gallery.signals import connect_member_signals

        connect_member_signals()
