from datetime import date, datetime
from uuid import UUID

from django.db import transaction
from django.db.models import Exists, OuterRef, Q, QuerySet

from features.songs.models.setlist import Setlist, SetlistItem
from features.songs.models.song import Played
from features.songs.setlist_dtos import SetlistDTO, SetlistItemDTO, SetlistItemInput


class SetlistRepositoryImpl:
    """Sunday setlists through the ORM (specs/017-sunday-setlist-push R-08, R-10, R-12)."""

    def replace(
        self, day: date, author_id: UUID, items: list[SetlistItemInput], saved_at: datetime
    ) -> tuple[SetlistDTO, bool]:
        """Create or fully replace the setlist of ``day``. ``True`` when one existed.

        The row lock serializes two saves of the same date, so the result is entirely one save's
        items, never a mix. ``last_reminder_slot`` is left alone on purpose.

        >>> SetlistRepositoryImpl().replace(date(2026, 10, 4), ana.pk, items, now)
        (SetlistDTO(date=datetime.date(2026, 10, 4), ...), False)
        """
        with transaction.atomic():
            setlist, created = Setlist.objects.get_or_create(
                date=day, defaults={"saved_by_id": author_id, "saved_at": saved_at}
            )
            setlist = Setlist.objects.select_for_update().get(pk=setlist.pk)
            setlist.items.all().delete()
            SetlistItem.objects.bulk_create(_rows(setlist, items))
            setlist.saved_by_id = author_id
            setlist.saved_at = saved_at
            setlist.save(update_fields=["saved_by", "saved_at"])
        stored = self.get_by_date(day)
        if stored is None:
            raise RuntimeError(f"Setlist {day.isoformat()} vanished right after being saved.")
        return stored, not created

    def get_by_date(self, day: date) -> SetlistDTO | None:
        """>>> SetlistRepositoryImpl().get_by_date(date(2026, 10, 4)).items[0].title
        'Grande é o Senhor'
        """
        setlist = _with_details(Setlist.objects.filter(date=day)).first()
        return _to_dto(setlist) if setlist else None

    def current(self, today: date) -> SetlistDTO | None:
        """Earliest setlist on or after ``today``.

        >>> SetlistRepositoryImpl().current(date(2026, 10, 1)).date
        datetime.date(2026, 10, 4)
        """
        upcoming = Setlist.objects.filter(date__gte=today).order_by("date")
        setlist = _with_details(upcoming).first()
        return _to_dto(setlist) if setlist else None

    def pending(self, today: date) -> list[SetlistDTO]:
        """Setlists on or before ``today`` with no ``Played`` row for their date, newest first.

        >>> SetlistRepositoryImpl().pending(date(2026, 10, 12))
        [SetlistDTO(date=datetime.date(2026, 10, 11), ...)]
        """
        played = Played.objects.filter(date=OuterRef("date"))
        rows = Setlist.objects.filter(~Exists(played), date__lte=today).order_by("-date")
        return [_to_dto(setlist) for setlist in _with_details(rows)]

    def has_plays(self, day: date) -> bool:
        """>>> SetlistRepositoryImpl().has_plays(date(2026, 10, 4))
        False
        """
        return Played.objects.filter(date=day).exists()

    def claim_reminder_slot(self, day: date, slot: datetime) -> bool:
        """Record ``slot`` as sent for the setlist of ``day``, unless it or a later one already
        is. One conditional UPDATE, so two overlapping runs cannot both win (FR-018).

        >>> SetlistRepositoryImpl().claim_reminder_slot(date(2026, 10, 4), slot)
        True
        """
        not_yet = Q(last_reminder_slot__isnull=True) | Q(last_reminder_slot__lt=slot)
        claimed = Setlist.objects.filter(not_yet, date=day).update(last_reminder_slot=slot)
        return claimed == 1


def _rows(setlist: Setlist, items: list[SetlistItemInput]) -> list[SetlistItem]:
    return [
        SetlistItem(setlist=setlist, position=i.position, song_id=i.song_id, tone=i.tone)
        for i in items
    ]


def _with_details(rows: QuerySet[Setlist]) -> QuerySet[Setlist]:
    return rows.select_related("saved_by__profile").prefetch_related("items__song")


def _to_dto(setlist: Setlist) -> SetlistDTO:
    items = sorted(setlist.items.all(), key=lambda item: item.position)
    return SetlistDTO(
        date=setlist.date,
        items=[_item_dto(item) for item in items],
        saved_by_name=_author_name(setlist),
        saved_at=setlist.saved_at,
    )


def _item_dto(item: SetlistItem) -> SetlistItemDTO:
    return SetlistItemDTO(
        position=item.position,
        song_id=item.song_id,
        title=item.song.title,
        artist=item.song.artist,
        tone=item.tone,
    )


def _author_name(setlist: Setlist) -> str | None:
    author = setlist.saved_by
    if author is None:
        return None
    profile = getattr(author, "profile", None)
    return getattr(profile, "name", "") or author.get_username()
