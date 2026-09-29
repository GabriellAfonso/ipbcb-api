from django.db.models import Q

from features.gallery.models.gallery import Album, Photo


class GalleryTrashedFileLookup:
    """Answers the media check's ``TrashedMediaLookup`` port (``features/media``), structurally:
    nothing here imports that feature, and ``config/di.py`` wires the two together
    (specs/014-gallery-trash-sync research R-05).

    One query: a ``UNION ALL`` over the trashed photos (original or thumbnail) and the trashed
    albums (cover), each served by a partial index that holds trashed rows only. The stored name
    is the media path, pre-013 ``gallery/{slug}/{filename}`` paths included.
    """

    def is_trashed(self, relative_path: str) -> bool:
        """>>> lookup.is_trashed("gallery/7/9b1e.jpg")
        True
        """
        # `order_by()` clears Meta.ordering: a compound statement allows no ORDER BY in its parts.
        photos = (
            Photo.all_objects.filter(deleted_at__isnull=False)
            .filter(Q(image=relative_path) | Q(thumbnail=relative_path))
            .order_by()
            .values("id")
        )
        covers = (
            Album.all_objects.filter(deleted_at__isnull=False, cover_image=relative_path)
            .order_by()
            .values("id")
        )
        return bool(list(photos.union(covers, all=True)[:1]))
