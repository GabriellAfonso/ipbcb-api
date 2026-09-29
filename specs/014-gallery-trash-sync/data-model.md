# Data Model: Gallery Trash and Change Feed

State after migration `gallery/0004` (generated, R-15). The fields that 013 added are unchanged
unless listed here.

## Album (extended)

| Field | Type | Notes |
|-------|------|-------|
| deleted_at | DateTimeField, null | set ⇔ trashed |
| deletion_batch | FK → GalleryDeletionBatch, null, PROTECT, `related_name="albums"` | set and cleared with `deleted_at` |
| updated_at | DateTimeField, `default=timezone.now`, indexed | set by every write (R-06) |

Managers: `objects = LiveAlbumManager()` (live only, the default) and
`all_objects = models.Manager()` (everything, used only by the trash, restore, purge and media
lookup repositories).

Constraints (replacing the 013 pair):

| Name | Fields | Condition |
|------|--------|-----------|
| `unique_live_album_name_per_parent` | `parent`, `name` | `parent IS NOT NULL AND deleted_at IS NULL` |
| `unique_live_root_album_name` | `name` | `parent IS NULL AND deleted_at IS NULL` |

Indexes: `album_parent_position` (kept), `album_updated_at`, and
`album_trashed_cover` (`cover_image`, `WHERE deleted_at IS NOT NULL`).

## Photo (extended)

| Field | Type | Notes |
|-------|------|-------|
| album | FK → Album | **PROTECT** (was CASCADE, R-09) |
| deleted_at | DateTimeField, null | set ⇔ trashed |
| deletion_batch | FK → GalleryDeletionBatch, null, PROTECT, `related_name="photos"` | |
| updated_at | DateTimeField, `default=timezone.now`, indexed | |

Managers: as Album (`LivePhotoManager`, `all_objects`).

Indexes: `photo_album_position` (kept), `photo_updated_at`,
`photo_trashed_image` (`image`, `WHERE deleted_at IS NOT NULL`),
`photo_trashed_thumbnail` (`thumbnail`, `WHERE deleted_at IS NOT NULL`).

## GalleryDeletionBatch (new)

Everything one delete action trashed.

| Field | Type | Notes |
|-------|------|-------|
| id | UUIDField, PK, `default=uuid4` | the `batch` of the log lines |
| root_kind | CharField(5), choices `album` / `photo` | |
| root_id | PositiveIntegerField | id of the item the action was taken on; no FK (R-01) |
| deleted_at | DateTimeField, indexed | the purge selects on it |
| deleted_by | FK → User, null, SET_NULL, `related_name="+"` | |

`Meta.ordering = ["-deleted_at", "id"]`, `verbose_name = "gallery deletion batch"`,
`__str__` → `"{root_kind} {root_id} @ {deleted_at}"`. Unique on `(root_kind, root_id)`: an item
roots at most one batch while it is in the trash.

Lifecycle: created by a delete → deleted by the restore of its root, or by the purge after its
rows.

## GalleryDeletionMark (new)

What the change feed reports as deleted. It outlives the row.

| Field | Type | Notes |
|-------|------|-------|
| id | BigAutoField | |
| kind | CharField(5), choices `album` / `photo` | |
| object_id | PositiveIntegerField | no FK: survives the purge |
| deleted_at | DateTimeField, indexed | |

Unique on `(kind, object_id)`. `Meta.ordering = ["deleted_at", "id"]`.

Lifecycle: upserted by a delete (one per trashed row) → deleted by the restore of that row, or
by the daily command once `deleted_at` is older than `MARK_RETENTION`.

## Item states

```
          DELETE (root or cascade)                purge (deleted_at + 30 d passed)
  live ─────────────────────────────▶ trashed ─────────────────────────────────▶ gone
    ▲                                   │                                   (mark stays
    └──────── restore of batch root ────┘                                    until 90 d)
```

- Every write of 013 on a trashed row, or under a trashed album, is `404`.
- Only the batch root can be restored. A cascaded member comes back with its root, never alone.

## Constants (`features/gallery/domain/trash_rules.py`)

| Name | Value | Used by |
|------|-------|---------|
| `TRASH_RETENTION` | `timedelta(days=30)` | purge, `purge_on` |
| `MARK_RETENTION` | `timedelta(days=90)` | feed full-sync threshold, mark expiry |
| `CURSOR_OVERLAP` | `timedelta(seconds=90)` | feed (R-07); above gunicorn's 60 s timeout |

## DTOs (`features/gallery/dtos/`)

Existing, extended:

- `AlbumRecord` + `updated_at: datetime`.
- `AlbumView` + `position: int`, `updated_at: datetime` (the second one is not serialized).
- `PhotoView` + `position: int`, `updated_at: datetime` (not serialized).

New (`trash_dtos.py`):

```python
class TrashedItemKind(StrEnum): ALBUM = "album"; PHOTO = "photo"

class TrashEntry(StrictBaseModel):
    kind: TrashedItemKind
    id: int
    name: str
    deleted_at: datetime
    deleted_by: str | None
    uploaded_by: str | None
    purge_on: date
    sub_album_count: int
    photo_count: int
    thumbnail_path: str | None

class TrashOutcome(StrictBaseModel):          # what a delete or restore touched, for the log
    batch_id: UUID
    kind: TrashedItemKind
    root_id: int
    album_ids: list[int]
    photo_ids: list[int]

class PurgeReport(StrictBaseModel):
    batches: int
    albums: int
    photos: int
    skipped_batch_ids: list[UUID]
    marks_expired: int
```

New (`feed_dtos.py`):

```python
class FeedCursor(StrictBaseModel):            # decoded; never leaves the service
    issued_at: datetime

class ChangeFeed(StrictBaseModel):
    albums: list[AlbumView]
    photos: list[PhotoView]
    deleted_album_ids: list[int]
    deleted_photo_ids: list[int]
    cursor: str
    full_sync_required: bool
```

## Repository interfaces (additions to `repositories/interfaces.py`)

```python
class TrashRepository(Protocol):
    def create_batch(self, kind: TrashedItemKind, root_id: int, actor_id: UUID | None) -> UUID: ...
    def trash_albums(self, album_ids: Sequence[int], batch_id: UUID) -> list[int]: ...
    def trash_photos_of_albums(self, album_ids: Sequence[int], batch_id: UUID) -> list[int]: ...
    def trash_photo(self, photo_id: int, batch_id: UUID) -> bool: ...
    def batch_rooted_at(self, kind: TrashedItemKind, root_id: int) -> TrashedRoot | None: ...
    def restore_batch(self, batch_id: UUID) -> TrashOutcome: ...
    def list_entries(self) -> list[TrashEntryRow]: ...
    def expired_batch_ids(self, before: datetime) -> list[UUID]: ...
    def purge_batch(self, batch_id: UUID) -> PurgedBatch: ...   # rows only; returns file names

class DeletionMarkRepository(Protocol):
    def upsert(self, kind: TrashedItemKind, ids: Sequence[int]) -> None: ...
    def remove(self, kind: TrashedItemKind, ids: Sequence[int]) -> None: ...
    def ids_since(self, kind: TrashedItemKind, since: datetime) -> list[int]: ...
    def expire(self, before: datetime) -> int: ...
```

Changed: `AlbumRepository` + `live_sibling_named(name, parent_id) -> int | None`,
`touch(ids)`, `touch_photos_of(album_id)`. `GalleryRepository` + `list_photos_changed_since(since)`.
`next_position` / `_next_photo_position` raise `AlbumNotFoundError` when the locked row is gone
(R-02). `apply_order` writes only the rows whose position changed and sets their `updated_at`.

Media port (`features/media/repositories/interfaces.py`):

```python
class TrashedMediaLookup(Protocol):
    def is_trashed(self, relative_path: str) -> bool: ...
```

`MediaViewer` + `can_own_gallery: bool = False`.

## Domain exceptions (`core/domain/exceptions.py`)

| Exception | Base | Status | `extra_context` |
|-----------|------|--------|-----------------|
| `TrashEntryNotFoundError(kind, item_id)` | `NotFoundError` | 404 | `kind`, `id` |
| `TrashedParentError(kind, item_id, parent_album_id)` | `ValidationError` | 400 | `kind`, `id`, `trashed_parent_id` |
| `AlbumRestoreNameConflictError(album_id, name, sibling_id)` | `ValidationError` | 400 | `album_id`, `name`, `conflicting_album_id` |
| `MediaFileTrashedError(path)` | `MediaFileNotFoundError` | 404 | none (paths are never echoed) |

Deleting an album or photo that is missing or already trashed reuses `AlbumNotFoundError` /
`PhotoNotFoundError`: to the caller a trashed item does not exist (FR-004).
