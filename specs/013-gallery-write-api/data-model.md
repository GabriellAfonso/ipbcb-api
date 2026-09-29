# Data Model: Gallery Write API

## Album (extended)

| Field        | Type                          | Constraints / default                                  |
|--------------|-------------------------------|--------------------------------------------------------|
| id           | BigAutoField (PK)             | unchanged                                              |
| name         | CharField(100)                | **no longer `unique=True`**; see constraints           |
| parent       | FK → Album, null              | `on_delete=PROTECT`, `related_name="children"`         |
| description  | TextField                     | `blank=True`, default `""`                             |
| event_date   | DateField                     | `null=True`, `blank=True`                              |
| position     | PositiveIntegerField          | default `0`; among siblings                            |
| cover_image  | ImageField                    | `blank=True`; name set by storage, `gallery/covers/{album_id}/{hex}.jpg` |

**Meta**: `ordering = ["position", "id"]`, `verbose_name = "album"`,
`verbose_name_plural = "albums"`.

**Constraints**:

- `unique_album_name_per_parent` — `UniqueConstraint(fields=["parent", "name"], condition=Q(parent__isnull=False))`
- `unique_root_album_name` — `UniqueConstraint(fields=["name"], condition=Q(parent__isnull=True))`

**Indexes**: `(parent, position)`.

**Invariants** (service-enforced, R-02): no album is its own ancestor. Name trimmed, non-blank.

## Photo (extended)

| Field       | Type                 | Constraints / default                                        |
|-------------|----------------------|--------------------------------------------------------------|
| id          | BigAutoField (PK)    | unchanged                                                    |
| album       | FK → Album           | CASCADE, `related_name="photos"` (unchanged)                 |
| name        | CharField(100)       | original filename, cut keeping extension                     |
| description | TextField            | `blank=True` (unchanged)                                     |
| image       | ImageField           | new uploads `gallery/{album_id}/{hex}.{ext}`; old keep path  |
| thumbnail   | ImageField           | `blank=True`; `gallery/thumbs/{album_id}/{hex}.jpg`          |
| date_taken  | DateField            | null (unchanged); EXIF date on upload                        |
| uploaded_at | DateTimeField        | `auto_now_add` (unchanged)                                   |
| uploaded_by | FK → `AUTH_USER_MODEL`, null | `on_delete=SET_NULL`, `related_name="+"`; never serialized |
| position    | PositiveIntegerField | default `0`; within album                                    |

**Meta**: `ordering = ["position", "id"]`, `verbose_name = "photo"`,
`verbose_name_plural = "photos"`.

**Indexes**: `(album, position)`.

`photo_upload_path` stays in `models/gallery.py` (referenced by `0001_initial`), now returning
`gallery/{album_id}/{uuid hex}.{ext}`.

## Role groups (core, data only)

| Group    | Before (0005)      | After (0006)      |
|----------|--------------------|-------------------|
| `leader` | `gallery__manage`  | `gallery__owner`  |
| `media`  | `gallery__manage`  | `gallery__owner`  |
| `admin`  | nothing stored     | nothing stored    |

## Migrations

| Migration | Kind | Content |
|-----------|------|---------|
| `gallery/0002_…` | generated (`makemigrations gallery`) | all field, constraint and index changes above; drops the `name` unique index |
| `gallery/0003_backfill_positions.py` | data, reason at top | roots by `name` → 0..n-1; photos per album by `(uploaded_at, id)` → 0..n-1. Reverse: no-op (positions are ignored by the previous schema) |
| `core/0006_gallery_owner_for_leader_media.py` | data, reason at top | swap `gallery__manage` → `gallery__owner` for leader, media; get-or-create permission rows. Reverse: opposite swap |

Existing albums satisfy both new constraints, since names were globally unique and every album
becomes a root. Both data migrations are verified against a restored production dump, with the
rollback actually run (CLAUDE.md §5; quickstart §3).

## Domain types (not persisted)

- `AlbumNode(id, parent_id, position, has_own_cover)` — input of `tree_order` /
  `resolve_cover_sources` (`features/gallery/domain/album_tree.py`).

## DTOs (`features/gallery/dtos/gallery_dtos.py`, Pydantic, `StrictBaseModel`)

| DTO | Fields |
|-----|--------|
| `AlbumView` | `id`, `name`, `parent_id`, `description`, `event_date`, `cover_path: str \| None`, `cover_source_album_id: int \| None` |
| `AlbumCreate` | `name`, `parent_id: int \| None = None`, `description = ""`, `event_date: date \| None = None` |
| `AlbumChanges` | same fields, all optional; `model_fields_set` says which were sent |
| `SiblingOrder` | `parent_id: int \| None`, `ids: list[int]` |
| `PhotoView` | `id`, `name`, `description`, `album_id`, `album_name`, `image_path`, `thumbnail_path: str \| None`, `date_taken`, `uploaded_at` |
| `PhotoChanges` | `name`, `description`, `date_taken`, `album_id`, all optional, via `model_fields_set` |
| `RejectedFile` | `filename`, `reason` |
| `UploadResult` | `accepted: list[PhotoView]`, `rejected: list[RejectedFile]` (replaces `created_count`/`errors`; `has_errors` kept for the admin page) |
| `ThumbnailBackfillReport` | `filled: int`, `skipped_ids: list[int]` |

`*_path` fields are URL paths from storage; views turn them into absolute URIs.
