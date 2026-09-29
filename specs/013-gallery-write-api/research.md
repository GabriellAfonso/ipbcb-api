# Research: Gallery Write API

Decisions behind [plan.md](plan.md). Each entry: decision, rationale, alternatives rejected.

---

## R-01 Sibling-unique album names, roots included

**Decision**: two conditional `UniqueConstraint`s on `Album`:

- `unique_album_name_per_parent`: `fields=["parent", "name"]`, `condition=Q(parent__isnull=False)`
- `unique_root_album_name`: `fields=["name"]`, `condition=Q(parent__isnull=True)`

The service also checks first (`AlbumRepository.sibling_name_taken`) to raise
`DuplicateAlbumNameError` with a readable message. The repository translates an
`IntegrityError` from either constraint into the same exception, for the race the pre-check
cannot see.

**Rationale**: SQL treats `NULL` as distinct from `NULL`, so a single `(parent, name)` unique
constraint lets any number of roots share a name — the exact regression the spec calls out.
Partial unique indexes exist on PostgreSQL (production) and SQLite (tests). Constraints in
`Meta.constraints` are also checked by `Model.validate_constraints()`, which a Django admin
`ModelForm` runs, so the admin is covered without extra code (spec FR-005).

**Alternatives**: service check only — the admin and any race bypass it. `nulls_distinct=False`
(Django 5+) — PostgreSQL 15+ only, and SQLite ignores it, so tests would not exercise the rule
production relies on.

Uniqueness is exact and case-sensitive after trimming (spec Edge Cases); no `Lower()` index.

---

## R-02 Cycle check and concurrent moves

**Decision**: a pure domain function
`find_cycle(album_id, new_parent_id, parent_of: Mapping[int, int | None]) -> list[int] | None`
walks up from `new_parent_id`; it returns the chain when it reaches `album_id`. The service loads
the whole `(id, parent_id)` map in one query (`AlbumRepository.parent_map(lock=True)`), inside
`transaction.atomic()`, with `select_for_update()` over the album rows.

**Rationale**: the gallery holds hundreds of albums, not millions; one query for the whole map
beats a query per ancestor (constitution: no queries in loops). Two concurrent moves, A under B
and B under A, each pass a check against stale data and together create a cycle. Locking the
album rows for the duration of a move serializes tree mutations on PostgreSQL; SQLite serializes
writers anyway. Moves are rare, so the lock costs nothing in practice.

**Alternatives**: recursive CTE — needs `.raw()`, forbidden. Materialized path column — makes
every move rewrite a subtree and duplicates what `parent` already says.

**Defence in depth**: every tree walk at read time (`resolve_covers`, `tree_order`) keeps a
visited set and stops at a repeat, so a cycle that reaches the database by any path (manual SQL,
a future bug) cannot hang a request.

---

## R-03 Positions

**Decision**: `position = PositiveIntegerField(default=0)` on `Album` and `Photo`, with
`Meta.ordering = ["position", "id"]` and indexes on `(parent, position)` / `(album, position)`.

- **Append**: `max(position) + 1` among the new siblings, computed inside the write
  transaction. The target parent album row (or the photo's album row) is locked with
  `select_for_update()`, so concurrent appends into one album serialize on PostgreSQL. Roots
  have no parent row to lock, so two roots created at the same instant may tie; ties break by id
  (spec Edge Cases).
- **Reorder**: the service compares the request's `ids` with the current sibling ids
  (`OrderMismatchError` on any difference, naming `missing`, `unexpected`, `repeated`), then the
  repository writes `position = index` for all of them with one `bulk_update` in one
  transaction.
- **Backfill**: a data migration numbers existing roots by `name` and each album's photos by
  `(uploaded_at, id)`, from 0.

**Alternatives**: fractional or gap-based positions — only pay off with move-one-item
endpoints, which are out of scope (full list only). Unlocked `max + 1` — accepted by the spec but
free to avoid where a row exists to lock.

---

## R-04 Image processing behind a project interface

**Decision**: `features/gallery/imaging/`:

- `interfaces.py` — `ImageProcessor` Protocol:
  - `pixel_count(source: IO[bytes]) -> int` — from the header, no decode
  - `bounded_jpeg(source, longest_side: int, quality: int) -> bytes`
  - `square_jpeg(source, side: int, quality: int) -> bytes`
  - `capture_date(source) -> date | None`
  - all raise `ImageProcessingError` (domain) on any decode failure, and leave the stream
    rewound.
- `pillow_image_processor.py` — `PillowImageProcessor`, the only module importing Pillow for
  derivatives.

Pipeline inside the implementation, shared by both derivatives: `Image.open` → first frame
(GIF) → `draft("RGB", target)` (JPEG decodes at reduced scale, cutting memory for big photos) →
`ImageOps.exif_transpose` → alpha composited onto white → `ImageOps.fit` (square, centered) or
`thumbnail` (bounded, never upscales) → `save(format="JPEG", quality=85, optimize=True)`.

EXIF date: `DateTimeOriginal` (0x9003) from the Exif IFD (0x8769), falling back to `DateTime`
(0x0132) in IFD0; format `YYYY:MM:DD HH:MM:SS`, date part only; anything malformed is `None`,
never an error.

Constants live in the service that uses them (spec: "single constant in the service"):
`COVER_SIDE_PX = 1000`, `THUMBNAIL_LONGEST_SIDE_PX = 1000`, `DERIVATIVE_JPEG_QUALITY = 85`,
`MAX_UPLOAD_PIXELS = 50_000_000`.

**Rationale**: CLAUDE.md §7 (third-party libs behind a thin owned interface) and testability —
services are unit-tested with a named `FakeImageProcessor`. Gallery is the only user today, so
the interface stays in the feature, not `core` (constitution: `core` only for what two features
share). `core.files.image_validation` stays untouched and runs first (spec FR-016).

**Order per file**: `detect_image_extension` (size, decode check, format) → `pixel_count` ≤ 50
MP → `bounded_jpeg` → store. `verify()` in validation does not decompress pixel data, and Pillow
itself refuses anything above ~179 MP at open (`DecompressionBombError`, mapped to
`ImageProcessingError`), so no step before the 50 MP check can exhaust memory.

**Alternatives**: `sorl-thumbnail` / `easy-thumbnails` — on-demand generation and a cache table,
neither needed when derivatives are made once at upload. `pillow-simd` — speed not a concern.

---

## R-05 File storage and failure ordering

**Decision**: `GalleryFileStorage` Protocol (`repositories/interfaces.py`) with
`DefaultStorageGalleryFileStorage` on Django's `default_storage`:

- `save_original(album_id, extension, stream) -> str` → `gallery/{album_id}/{uuid4 hex}.{ext}`
- `save_thumbnail(album_id, content: bytes) -> str` → `gallery/thumbs/{album_id}/{hex}.jpg`
- `save_cover(album_id, content: bytes) -> str` → `gallery/covers/{album_id}/{hex}.jpg`
- `delete(name)`, `open(name)`, `url(name)`

Order, as in `MemberPhotoService` (specs/010 R-05): files first, then the row(s) in one
transaction; if the transaction fails the new files are deleted; a replaced cover file is
deleted `on_commit`. A photo is never committed without both files.

`photo_upload_path` stays importable in `models/gallery.py` — `0001_initial` references it by
dotted path and would fail to load otherwise. It now returns the new scheme; nothing calls it
in normal flow, because rows receive the name the storage already wrote.

**Rationale**: storage cannot join a transaction; this order leaves no row pointing at a
missing file. Random names close the polyglot concern in `media_rules.py` for new uploads (the
extension now comes from the decoded format), and paths never depend on the album name (spec
FR-017).

---

## R-06 Cover resolution and tree order at read time

**Decision**: two pure functions in `features/gallery/domain/album_tree.py` over a list of
`AlbumNode(id, parent_id, position, has_own_cover)`:

- `tree_order(nodes) -> list[int]` — pre-order DFS, children sorted by `(position, id)`.
- `resolve_cover_sources(nodes) -> dict[int, int | None]` — memoized post-order: an album with
  its own cover is its own source; otherwise the source of its first child (by position, id)
  whose source is not `None`. This equals "first descendant with a cover in pre-order", in O(n).

Both keep a visited set (R-02). The service loads every album once, resolves, and builds
`AlbumView` DTOs with the source's cover URL path.

`GET /api/photos/` loads photos with `select_related("album")`, then sorts in Python by
`(rank_in_tree_order[album_id], position, id)`.

**Rationale**: inheritance is computed, never stored (spec FR-015), so nothing goes stale when a
sub-album's cover changes. The album table is small enough to load whole on every list.

**Alternatives**: stored `resolved_cover` column — must be recomputed up the chain on every
cover change, move, and future deletion. Ordering in SQL by tree — needs a recursive CTE.

---

## R-07 Mixed permissions on one route

`/api/albums/` (GET member, POST manage) and `/api/photos/` (GET member, POST manage) serve a
read and a write on one URL. DRF binds permissions per view, not per method.

**Decision**: those two views override `get_permissions()`: `GET` → `[IsMemberUser()]`, any
other method → `[IsAuthenticated(), scope_permission(Scope.GALLERY)()]`. One helper,
`member_read_gallery_write_permissions(method)`, in `features/gallery/views/permissions.py`,
unit-tested per method. Every other gallery write view uses the plain
`permission_classes = [IsAuthenticated, scope_permission(Scope.GALLERY)]`, like
`AdminMemberPhotoAPIView`.

**Rejected**: `scope_permission` alone — `GET` would require `view` on `gallery`, locking plain
members out of the gallery. Two URLs — breaks the route table the spec fixes.

---

## R-08 Request parsing, DTOs and "absent vs null"

- JSON bodies go through DRF serializers (constitution: input validated before the DB), then
  into Pydantic DTOs: `AlbumCreate`, `AlbumChanges`, `SiblingOrder`, `PhotoChanges`.
- `PATCH` must distinguish "`parent_id` absent" (do not move) from "`parent_id: null`" (move to
  root), and the same for `event_date` / `date_taken`. The DTOs are built from the serializer's
  `validated_data` (which only holds sent keys) and the service reads `model_fields_set`.
- Multipart `album_id` goes through `core.http.parsing.require_int`; files are
  `request.FILES.getlist("image")`. Missing either is `ValidationError` → canonical `400`.
- Photo `name` longer than 100 chars is cut keeping the extension (`domain/photo_names.py`).

---

## R-09 Error types and message language

New domain exceptions in `core/domain/exceptions.py`:

| Exception | Base | Status | Message language |
|-----------|------|--------|------------------|
| `AlbumNotFoundError(album_id)` | `NotFoundError` | 404 | English (like `SongsNotFoundError`) |
| `PhotoNotFoundError(photo_id)` | `NotFoundError` | 404 | English |
| `AlbumCycleError(album_id, parent_id, chain)` | `ValidationError` | 400 | Portuguese — reached from a normal move in the app |
| `DuplicateAlbumNameError(name, parent_id)` | `ValidationError` | 400 | Portuguese — reached from a normal create/rename |
| `OrderMismatchError(missing, unexpected, repeated)` | `ValidationError` | 400 | English — only a client bug reaches it |
| `NoPhotoAcceptedError(rejected)` | `ValidationError` | 400 | Portuguese `detail`; `extra_context()` returns `{"rejected": [...]}` |
| `ImageProcessingError(filename)` | `ValidationError` | 400 (cover `PUT`) / per-file reason (upload) | Portuguese |
| `ImageTooLargeError(width, height, max_pixels)` | `ValidationError` | 400 (cover `PUT`) / per-file reason (upload) | Portuguese — 50 MP limit (clarification Q3) |

`extra_context()` already exists on `DomainError` and is merged into the canonical body by the
handler, so the every-file-rejected `400` (clarification Q1) needs no handler change.
`OrderMismatchError` and `AlbumCycleError` also expose their ids through `extra_context()`.

Duplicate name is `400` (spec), not `409`: it subclasses `ValidationError`, not `ConflictError`.

---

## R-10 Raising Liderança and Mídia to `owner` on `gallery`

**Decision**: `core/migrations/0006_gallery_owner_for_leader_media.py`, data migration, reason
at the top. Forward: for groups `leader` and `media`, add `gallery__owner` and remove
`gallery__manage` (only the highest level per scope is stored — 0005's convention). Permission
rows are get-or-created, as 0005 does, because `post_migrate` runs too late on a fresh database.
Reverse: the opposite swap — a real rollback, run in the migration test.

**Rationale**: levels live in the role groups (012 D-1), so code cannot change them; 0005 must
not be edited (already applied in production — CLAUDE.md §5).

Tests that pin the old level move with it: `core/tests/integration/test_panel_roles_seed.py`
and `test_management_access_matrix.py` (gallery row). Unit tests that use `gallery__manage` as
arbitrary fake data stay.

---

## R-11 Django admin

- `AlbumAdmin`: fields `name`, `parent`, `description`, `event_date`; `cover_image` and
  `position` read-only. Its form's `clean()` calls `AlbumService.validate_placement()` (cycle +
  duplicate) and `save_model()` calls `AlbumService.create/update`, so positions append and the
  rules are the API's. `features.gallery.admin` joins the DI wiring list.
- `Album.parent` is `on_delete=PROTECT`: deleting an album with sub-albums fails in the admin
  with Django's protected-objects page (spec Assumptions; deletion is 014).
- `PhotoAdmin`: `has_add_permission` → `False` (photos arrive only through the upload page, so
  every photo has a thumbnail); `image`, `thumbnail`, `uploaded_by`, `position` read-only.
- Upload page: unchanged URL and form; passes `request.user.pk` as uploader; renders
  `"{filename}: {reason}"` for each rejected file, as today.

---

## R-12 Read responses and caching

Gallery reads return plain `Response` like the two existing gallery endpoints — no ETag
helper. The body does not depend on who asks (only whether they may ask), so the constitution's
`private` rule does not apply; no shared cache sits in front of the API. Writes return no cache
headers.

`image_url`, `thumbnail_url`, `cover_url` are built with `request.build_absolute_uri(url_path)`,
same as `image_url` today. All three live under `gallery/`, served by the unchanged spec 009
rule.

---

## R-13 Thumbnail backfill command

`python manage.py generate_photo_thumbnails` → `GalleryService.fill_missing_thumbnails()`:
iterates photos with an empty `thumbnail` in id order, in batches of 100 (`iterator`), opens the
original through `GalleryFileStorage.open`, generates and saves the thumbnail, updates that row.
A missing or undecodable original is recorded in the report and skipped. Output: plain text
summary (`filled N, skipped M: ids …`). Idempotent because it selects only empty thumbnails.
One write per photo is inherent to a backfill; reads are batched.

---

## R-14 Housekeeping

- `features/media/domain/media_rules.py` comment "Gallery uploads keep their original filename"
  → now true only for photos uploaded before 013; the explicit content-type table stays.
- `specs/gallery/plan.md` "No service/repository layer" is stale (the layers exist); rewritten
  with the domain spec (spec FR-021).
