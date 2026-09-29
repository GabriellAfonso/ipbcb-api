---

description: "Task list for Gallery Trash and Change Feed"
---

# Tasks: Gallery Trash and Change Feed

**Input**: Design documents from `specs/014-gallery-trash-sync/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md,
contracts/gallery-trash-api.md, quickstart.md

**Tests**: Included. CLAUDE.md §10 requires a test for every new function. The request asks for
regression tests covering cascade and exact batch restore, name reuse, invisibility, the media
rule, purge order and the feed across a purge. Fakes are named classes in
`server/features/gallery/tests/fakes.py` and `server/features/media/tests/fakes.py`, never inline
stubs.

**Organization**: Tasks are grouped by user story (US1–US6 from spec.md). Paths are relative to
the repository root. Run commands from `server/` with `.venv_windows` active (PowerShell).

**Commit rule**: The mypy pre-commit hook checks the whole tree, so every commit must leave it
type-correct. Tasks that must land in the same commit say so. Spec and code go together
(CLAUDE.md §6.2): the Phase 1 docs are committed with the first code commit of Phase 2.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1–US6 from spec.md

---

## Phase 1: Setup

**Purpose**: A known-green baseline, and the specs updated to the target state before any code.

- [X] T001 Run `pytest` and `mypy .` from `server/` on branch `014-gallery-trash-sync` and confirm both pass before any change
- [X] T002 Rewrite `specs/gallery/spec.md` to the state this feature produces (spec FR-040):
  - Album/Photo gain `deleted_at`, `deletion_batch`, `updated_at`.
  - `Photo.album` is `PROTECT`.
  - Sibling-name uniqueness applies to live albums only.
  - New models `GalleryDeletionBatch` and `GalleryDeletionMark`.
  - Endpoint table gains `DELETE /api/albums/{id}/`, `DELETE /api/photos/{id}/`, `GET /api/gallery/trash/`, the two restore routes and `GET /api/gallery/changes/`, with their permissions.
  - Album and Photo resources gain `position`.
  - New sections Trash, Restore, Purge (30 days, command `purge_gallery_trash`, host cron) and Change feed (cursor, 90 s overlap, 90-day marks, `full_sync_required`).
  - The media paragraph now says files of trashed items are `404` to members and readable by owners.
  - Admin: no delete on albums or photos.
  - Errors table gains the restore refusals.
  - Remove "Deletion as a feature belongs to feature 014".
- [X] T003 [P] Rewrite `specs/gallery/plan.md` (reference the decisions D-1…D-16 of `specs/014-gallery-trash-sync/plan.md`) and `specs/gallery/tasks.md` (only what stays missing after 014: member tagging → 015; the orphan-file listing command, not planned)
- [X] T004 [P] Amend `specs/009-protected-media-access/spec.md` (spec FR-041):
  - FR-005 `gallery` row: "members; files of trashed gallery items only with `owner` on `gallery` (spec 014)".
  - FR-009: "except `gallery/`, where a trashed row hides its files (spec 014)".
  - Edge case "Orphan files": still served, but files of trashed rows are not.
  - Assumption "No database lookup": scoped to folders other than `gallery/`.
  - Add a note under the superseded-terms banner pointing to spec 014.
- [X] T005 [P] Amend `specs/012-feature-role-permissions/spec.md` (spec FR-042): add a `### gallery` section to Endpoint Classification listing the 013 writes and the 014 routes:
  - `DELETE api/albums/{id}/` and `DELETE api/photos/{id}/` at `owner`, default.
  - `GET api/gallery/trash/` at `owner`, override.
  - `POST api/gallery/trash/albums/{id}/restore/` and `POST api/gallery/trash/photos/{id}/restore/` at `owner`, override.
  - A note that `GET api/gallery/changes/` is a member endpoint outside the classification.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The schema, managers, clock injection, `position` on resources, pure rules,
exceptions and exact cover-change tracking. After this phase every 013 read ignores trashed rows
and every write sets `updated_at`, but nothing can trash a row yet.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

### Domain

- [X] T006 [P] Create `server/features/gallery/domain/trash_rules.py` (research R-03, R-09):
  - Constants `TRASH_RETENTION = timedelta(days=30)`, `MARK_RETENTION = timedelta(days=90)` and `CURSOR_OVERLAP = timedelta(seconds=90)`, the last with a comment naming gunicorn's 60 s timeout as the reason.
  - `subtree_ids(root_id, parent_of: Mapping[int, int | None]) -> list[int]`: root plus every descendant, with a visited set so it is cycle-safe.
  - `purge_order(album_ids: Collection[int], parent_of) -> list[int]`: deepest first within the given set.
  - `purge_on(deleted_at: datetime) -> date`: UTC date of `deleted_at + TRASH_RETENTION`.
  - Docstring with an example on each.
- [X] T007 [P] Test T006 in `server/features/gallery/tests/unit/test_trash_rules.py`:
  - subtree of a leaf, a root, a middle node;
  - a cycle in the input terminates;
  - purge order puts C before B before A for A → B → C;
  - siblings stay in any order but after their children;
  - `purge_on` crosses a month boundary in UTC.
- [X] T008 [P] Create `server/features/gallery/domain/feed_cursor.py` (research R-07):
  - `encode_cursor(issued_at: datetime) -> str` returns `"v1." + base64url(int microseconds since epoch, 8 bytes big-endian)`, without padding.
  - `decode_cursor(raw: str) -> datetime | None` returns `None` for unknown version, bad base64, wrong length or non-ASCII input.
  - `feed_window_start(since: datetime) -> datetime` returns `since - CURSOR_OVERLAP`.
  - `requires_full_sync(since: datetime | None, now: datetime) -> bool` is true for `None` from a bad decode, `since > now + CURSOR_OVERLAP`, and `since < now - MARK_RETENTION + CURSOR_OVERLAP`.
  - Document that a missing `since` is not a full-sync-required case; the service tells "absent" from "unreadable".
- [X] T009 [P] Test T008 in `server/features/gallery/tests/unit/test_feed_cursor.py`:
  - round trip keeps microseconds;
  - `v2.` prefix, garbage, empty string and a 7-byte payload each give `None`;
  - window start is 90 s earlier;
  - full-sync thresholds at exactly 90 days, 90 days minus 1 s, and 91 s in the future.
- [X] T010 [P] Add `changed_cover_albums(before: Mapping[int, str | None], after: Mapping[int, str | None]) -> set[int]` to `server/features/gallery/domain/album_tree.py`. Both maps go from album id to the resolved cover *file name* (`None` without one). Return the ids present in `after` whose value differs from `before`, or that are new. Add a sibling helper `resolved_cover_names(nodes, cover_names: Mapping[int, str]) -> dict[int, str | None]` built on `resolve_cover_sources` (research R-06).
- [X] T011 [P] Test T010 in `server/features/gallery/tests/unit/test_album_tree.py`: an own cover replaced (same source, new name) → changed; a descendant cover source trashed (absent from `after`) → ancestors changed; reorder making another child first → parent changed; unrelated album → unchanged
- [X] T012 [P] Add to `server/core/domain/exceptions.py` (data-model.md, research R-04):
  - `TrashEntryNotFoundError(kind, item_id)` (`NotFoundError`): English message `"No trash entry for {kind} {item_id}; only the item a delete was made on can be restored."`, `extra_context` → `kind`, `id`.
  - `TrashedParentError(kind, item_id, parent_album_id)` (`ValidationError`): Portuguese message per contracts/gallery-trash-api.md, `extra_context` → `kind`, `id`, `trashed_parent_id`.
  - `AlbumRestoreNameConflictError(album_id, name, sibling_id)` (`ValidationError`): Portuguese message per the contract, `extra_context` → `album_id`, `name`, `conflicting_album_id`.
  - `MediaFileTrashedError(MediaFileNotFoundError)`: no extra context, never echoes the path.
  - A docstring with an example on each. The file must stay under 500 lines.
- [X] T013 [P] Test T012 in `server/core/tests/unit/test_gallery_trash_exceptions.py`: messages contain the offending values; `custom_exception_handler` maps them to 404/400 with `error_code` and the `extra_context` keys; `MediaFileTrashedError` is an instance of `MediaFileNotFoundError`

### Schema and managers

- [X] T014 Create `server/features/gallery/models/trash.py` (data-model.md) with the two models:
  - `GalleryDeletionBatch`: `id` UUID PK `default=uuid4`, `root_kind` CharField(5) choices album/photo, `root_id` PositiveIntegerField, `deleted_at` indexed, `deleted_by` FK user null `SET_NULL` `related_name="+"`; unique `(root_kind, root_id)`; `Meta.ordering = ["-deleted_at", "id"]`, verbose names, `__str__`.
  - `GalleryDeletionMark`: BigAutoField, `kind` CharField(5) choices, `object_id` PositiveIntegerField, `deleted_at` indexed; unique `(kind, object_id)`; ordering `["deleted_at", "id"]`, verbose names, `__str__`.
  - A `TrashedItemKind` `TextChoices`, reused by the DTO enum in T021.
- [X] T015 Change `server/features/gallery/models/gallery.py` (data-model.md, research R-02):
  - `LiveAlbumManager` and `LivePhotoManager` (`get_queryset().filter(deleted_at__isnull=True)`) declared first as `objects`, plus `all_objects = models.Manager()`, with a comment on why hiding is the default.
  - `deleted_at`, `deletion_batch` (FK `GalleryDeletionBatch` null `PROTECT`, `related_name="albums"` / `"photos"`) and `updated_at` (`default=timezone.now`, `db_index=True`) on both models.
  - `Photo.album` `on_delete=PROTECT`, with a comment citing research R-09.
  - Constraints renamed to `unique_live_album_name_per_parent` / `unique_live_root_album_name`, conditions `& Q(deleted_at__isnull=True)`.
  - Partial indexes `album_trashed_cover` (`cover_image`), `photo_trashed_image`, `photo_trashed_thumbnail`, all with `condition=Q(deleted_at__isnull=False)`.
  - Update the `_DUPLICATE_NAME_MARKERS` in `server/features/gallery/repositories/album_repository.py` to the new constraint names, in the same commit.
- [X] T016 Run `python manage.py makemigrations gallery` → `server/features/gallery/migrations/0004_*.py`. Review it (CreateModel ×2, AddField ×6, AlterField `Photo.album`, RemoveConstraint ×2, AddConstraint ×2, AddIndex, AlterModelManagers) and do not hand-edit it. Confirm `python manage.py makemigrations --check --dry-run` is clean (the CI gate).
- [X] T017 [P] **Regression** tests in `server/features/gallery/tests/integration/test_album_constraints.py`:
  - a root named "Culto" with `deleted_at` set does not block a live root "Culto", and the same holds under a parent;
  - two live siblings with one name still raise `IntegrityError`;
  - `Album.objects` excludes the trashed one and `Album.all_objects` includes it;
  - deleting an album that still has a photo row raises `ProtectedError`.
- [X] T018 [P] Migration test in `server/features/gallery/tests/integration/test_trash_schema_migration.py` with `MigrationExecutor` (pattern of `test_position_backfill_migration.py`): rows created at 0003 get a non-null `updated_at` and `deleted_at IS NULL` at 0004; migrating back to 0003 and forward again succeeds

### Clock, `updated_at`, `position`, lock safety

- [X] T019 Change `server/features/gallery/repositories/album_repository.py` and `gallery_repository.py` (research R-02, R-06):
  - Constructors take `clock: Clock` (from `core.time.clock`).
  - Every write sets `updated_at=self._clock.now()`: `create` / `create_photo` too, and `update`, `update_photo`, `move_photo`, `set_cover_name`, `set_cover_name_if_absent`, `set_thumbnail`.
  - `apply_order` reads current positions and `bulk_update`s only the rows whose position changes, with `updated_at`.
  - `next_position` and `_next_photo_position` raise `AlbumNotFoundError(album_id)` when the `select_for_update` lock query returns no row. Comment: a live-manager lock re-evaluates `deleted_at` after waiting, so a concurrently trashed album yields nothing.
  - `_RECORD_FIELDS` gains `updated_at`.
  - `AlbumRecord` gains `updated_at: datetime`, and `_to_view` fills `position` and `updated_at` on `PhotoView`.
  - Same commit as T020–T022.
- [X] T020 Add to `AlbumRepository` (Protocol in `server/features/gallery/repositories/interfaces.py` and impl):
  - `touch(ids: Sequence[int]) -> None`: sets `updated_at` on the live albums.
  - `touch_photos_of(album_id) -> None`: sets `updated_at` on the album's live photos.
  - `live_sibling_named(name, parent_id) -> int | None`: id of the live sibling holding `name`.

  Add to `GalleryRepository`:
  - `list_photos_changed_since(since: datetime) -> list[PhotoView]`: live photos with `updated_at > since`, `select_related("album")`, ordered by `position, id`.
- [X] T021 Extend `server/features/gallery/dtos/gallery_dtos.py`: `AlbumView` + `position: int`, `updated_at: datetime`; `PhotoView` + `position: int`, `updated_at: datetime`; `AlbumService._view` fills them from the record. Create `server/features/gallery/dtos/trash_dtos.py` (`TrashedItemKind` StrEnum, `TrashEntry`, `TrashOutcome`, `PurgeReport`) and `server/features/gallery/dtos/feed_dtos.py` (`ChangeFeed`) per data-model.md
- [X] T022 Reorder `server/config/di.py` so `clock` is declared before the gallery providers, and pass `clock=clock` to `album_repository` and `gallery_repository`. Same commit as T019.
- [X] T023 [P] Add `position` (IntegerField, last field) to `AlbumSerializer` in `server/features/gallery/serializers/album_serializers.py` and `PhotoSerializer` in `server/features/gallery/serializers/serializers.py`, with docstrings updated ("`position` added by feature 014"). Update `server/features/gallery/tests/integration/test_gallery_legacy_reads.py`: every old key is kept, and `position` is the only addition besides `thumbnail_url`.
- [X] T024 Update `server/features/gallery/tests/fakes.py`:
  - `FakeClock` (settable `now`, `advance(timedelta)`).
  - `FakeAlbumRepository` and `FakeGalleryRepository` gain `updated_at` bookkeeping, `touch`, `touch_photos_of`, `live_sibling_named`, `list_photos_changed_since`, a `deleted_at` per row honoured by every read, and raise `AlbumNotFoundError` in `next_position` for a trashed album.

  Fix the existing unit tests that build `AlbumRecord` / `PhotoView` without the new fields.
- [X] T025 [P] Repository integration tests in `server/features/gallery/tests/integration/test_album_repository.py` and `test_gallery_repository.py` (fixed `FakeClock`):
  - every write sets `updated_at`;
  - `apply_order` leaves unchanged rows' `updated_at` alone;
  - `touch_photos_of` touches only that album's live photos;
  - `list_photos_changed_since` is strict (`>`) and excludes trashed rows;
  - **race regression**: with the album row trashed (`deleted_at` set) before `create_photo` / `move_photo` / `next_position`, each raises `AlbumNotFoundError` and inserts nothing.

### Cover-change tracking

- [X] T026 Create `server/features/gallery/services/cover_change_tracker.py`, class `CoverChangeTracker(album_repository)`:
  - `snapshot() -> dict[int, str | None]`: resolved cover names of every live album, from `list_records()` and T010.
  - `touch_changed(before: Mapping[int, str | None], also: Sequence[int] = ()) -> list[int]`: re-reads, computes `changed_cover_albums(before, after)`, calls `touch` on the result plus `also`, and returns the touched ids.

  Register it in `server/config/di.py`.
- [X] T027 Use T026 in `server/features/gallery/services/album_service.py` and `album_cover_service.py` (research R-06):
  - `create`, `update` (move) and `reorder` take a `snapshot()` inside their transaction before the write and call `touch_changed(before, also=[album_id])` after it.
  - A rename also calls `touch_photos_of(album_id)`.
  - `replace_cover`, `remove_cover` and `cover_from_photo` snapshot before `_switch_cover` / `set_cover_name_if_absent` and touch after.
  - Constructors gain `cover_tracker`; update the providers in `server/config/di.py` in the same commit.
- [X] T028 [P] Unit tests with fakes in `server/features/gallery/tests/unit/test_album_service.py` and `test_album_cover_service.py`: rename touches the album and its photos; a move touches old and new ancestors whose resolved cover changed and not unrelated albums; a reorder that changes the first child touches the parent; replacing a sub-album's cover touches the sub-album and inheriting ancestors (spec US3 scenario 11)

**Checkpoint**: The migration applies on a fresh database; every read hides rows with `deleted_at`
set; every write bumps `updated_at` exactly; resources carry `position`; the whole suite is green.

---

## Phase 3: User Story 1 - Delete a photo sent by mistake (Priority: P1) 🎯 MVP

**Goal**: `DELETE /api/photos/{id}/` trashes a photo in a one-photo batch with a deletion mark;
the photo disappears from every read, and its original and thumbnail become `404` to members
and stay readable by owners.

**Independent Test**: As Mídia, delete a photo. As a member, it is gone from both photo lists and
its two file URLs are `404`. As an owner, the same URLs are served.

### Implementation

- [X] T029 [US1] Add the `TrashRepository` and `DeletionMarkRepository` Protocols to `server/features/gallery/repositories/interfaces.py` (data-model.md), with only the methods US1 needs: `create_batch`, `trash_photo`; `upsert`. Later stories add theirs.
- [X] T030 [US1] Create `server/features/gallery/repositories/trash_repository.py`, class `TrashRepositoryImpl(clock)`:
  - `create_batch(kind, root_id, actor_id) -> UUID` inserts a `GalleryDeletionBatch` with `deleted_at=now`.
  - `trash_photo(photo_id, batch_id) -> bool` runs `Photo.objects.filter(pk=..., deleted_at__isnull=True).update(deleted_at=now, deletion_batch_id=batch_id, updated_at=now)` and returns whether a row changed. First it locks the photo's album row (`select_for_update` via `Album.objects`), so the call serializes with a concurrent move.
- [X] T031 [P] [US1] Create `server/features/gallery/repositories/deletion_mark_repository.py`, `DeletionMarkRepositoryImpl(clock)` with `upsert(kind, ids)` via one `GalleryDeletionMark.objects.bulk_create(..., update_conflicts=True, unique_fields=["kind", "object_id"], update_fields=["deleted_at"])` (research R-08)
- [X] T032 [US1] Add `FakeTrashRepository` and `FakeDeletionMarkRepository` to `server/features/gallery/tests/fakes.py` (in-memory batches and marks, operating on the rows of `FakeGalleryRepository` / `FakeAlbumRepository`)
- [X] T033 [US1] Create `server/features/gallery/services/gallery_trash_service.py`, class `GalleryTrashService(album_repository, gallery_repository, trash_repository, mark_repository, cover_tracker, file_storage, clock)`, with `delete_photo(photo_id, actor_id: UUID | None) -> TrashOutcome`. Inside `transaction.atomic()`:
  1. require the live photo (`PhotoNotFoundError` otherwise);
  2. `snapshot()`;
  3. `create_batch(PHOTO, photo_id, actor_id)`;
  4. `trash_photo`; if it returns `False`, raise `PhotoNotFoundError`, because a concurrent delete won;
  5. `upsert(PHOTO, [photo_id])`;
  6. `touch_changed(before)`.

  Log `gallery_trashed` with `kind`, `id`, `batch`, `actor_id`, `album_count=0`, `photo_count=1` (research R-14). Keep each method 4–20 lines.
- [X] T034 [US1] Register `trash_repository`, `deletion_mark_repository` and `gallery_trash_service` in `server/config/di.py`
- [X] T035 [US1] Unit tests in `server/features/gallery/tests/unit/test_gallery_trash_service.py` (fakes, `FakeClock`, `caplog`): photo trashed with batch and mark; second delete → `PhotoNotFoundError`, no new batch; unknown id → `PhotoNotFoundError`; one log line with the ids only, no name; no album is touched, since a photo delete never changes a resolved cover
- [X] T036 [US1] Add `delete()` to `PhotoDetailAPIView` in `server/features/gallery/views/gallery.py`. It keeps `GALLERY_WRITE`, whose `DELETE` default is `owner`, calls `gallery_trash_service.delete_photo(photo_id, request.user.pk)` and answers `204`. The module is already wired in `server/config/di.py`.
- [X] T037 [US1] Media port (research R-05):
  - Add `TrashedMediaLookup` Protocol (`is_trashed(relative_path: str) -> bool`) to `server/features/media/repositories/interfaces.py`.
  - Add `can_own_gallery: bool = False` to `MediaViewer` in `server/features/media/dtos/media_dtos.py`.
  - Add `TRASHED = "trashed"` to `MediaAccessOutcome` in `server/features/media/domain/media_rules.py`, and map `MediaFileTrashedError` to it in `_OUTCOME_BY_ERROR`.
- [X] T038 [US1] Change `MediaAccessService` in `server/features/media/services/media_access_service.py`: the constructor takes `trashed_lookup: TrashedMediaLookup`. `_viewer_may_read` becomes a small decision for the `gallery` folder, following the research R-05 table:
  - a member who is also an owner is allowed without a lookup;
  - a caller who is neither is forbidden without a lookup;
  - otherwise it looks up: a trashed file is allowed for an owner and raises `MediaFileTrashedError` for a member; a live file is allowed for a member and forbidden for a non-member owner.

  The check runs after the folder rule and before `_located_file`. Other folders are unchanged and never call the lookup. Each function 4–20 lines.
- [X] T039 [US1] Create `server/features/gallery/repositories/trashed_file_lookup.py`, `GalleryTrashedFileLookup.is_trashed(relative_path)`. It runs **one** query: `Photo.all_objects.filter(deleted_at__isnull=False).filter(Q(image=p) | Q(thumbnail=p)).values("id").union(Album.all_objects.filter(deleted_at__isnull=False, cover_image=p).values("id"), all=True)[:1]`, evaluated once. It imports nothing from `features.media`; a docstring names the Protocol it satisfies structurally.
- [X] T040 [US1] Wire the media port in `server/config/di.py`: `gallery_trashed_file_lookup = providers.Factory(GalleryTrashedFileLookup)`, `media_access_service` gets `trashed_lookup=gallery_trashed_file_lookup`. In `server/features/media/views/media_file.py`, `_viewer` sets `can_own_gallery=scope_permission(Scope.GALLERY, {"GET": Level.OWNER})().has_permission(request, self)`. Build that class once at module level. Same commit as T037–T039.
- [X] T041 [P] [US1] Add `FakeTrashedMediaLookup` (a set of trashed paths, records the calls) to `server/features/media/tests/fakes.py` and extend `server/features/media/tests/unit/test_media_access_service.py`:
  - the four rows of the research R-05 table;
  - a member+owner makes zero lookup calls, and so does a non-gallery folder;
  - a trashed file is logged with the outcome `trashed`;
  - the 009 order is kept: a non-member non-owner gets 403 on a missing file, without a lookup.
- [X] T042 [P] [US1] **Regression** integration test `server/features/gallery/tests/integration/test_media_trashed_gallery_files.py` (with the gallery tests: it builds gallery rows and features never import each other; it reaches the media check only through its URL) (temporary `MEDIA_ROOT`, real files):
  - a trashed photo's original and thumbnail → member `404`, owner `200` with `X-Accel-Redirect`;
  - a photo with a pre-013 path `gallery/retiro-2025/IMG_0042.jpg` trashed → member `404`;
  - a live photo → member `200`;
  - an orphan file with no row → member `200` (clarified);
  - `profiles/` and `members/` responses unchanged;
  - `django_assert_max_num_queries` shows at most one extra query for a member request.
- [X] T043 [P] [US1] API tests in `server/features/gallery/tests/integration/test_trash_api.py` (photo part): `DELETE /api/photos/{id}/` → `204`; photo absent from `GET /api/photos/` and `GET /api/albums/{id}/photos/`; second `DELETE` → `404`; `PATCH` of the trashed photo → `404`; the trashed id in `PUT /api/albums/{id}/photos/order/` → `400` with it in `unexpected`; row and files still exist (spec US1 scenarios 1, 4, 6, 7)
- [X] T044 [P] [US1] Add rows for `DELETE /api/photos/{id}/` to `server/features/gallery/tests/integration/test_gallery_access.py`: Admin, Liderança and Mídia get `204`; a member without a role and a non-member get `403` whether or not the photo exists; anonymous gets `401`

**Checkpoint**: A mistaken photo can be removed from the app and stops being downloadable. MVP.

---

## Phase 4: User Story 2 - Delete an album and everything under it (Priority: P1)

**Goal**: `DELETE /api/albums/{id}/` trashes the album, its live descendants and their live
photos in one batch, with one mark per row, and the subtree disappears from every read,
resolved cover included.

**Independent Test**: A → B → C with photos at each level; delete A; none of them appears in any
read; the parent's resolved cover moves on; a new "Culto" can take A's name.

### Implementation

- [X] T045 [US2] Add to `TrashRepository` (Protocol and impl in `server/features/gallery/repositories/trash_repository.py`):
  - `trash_albums(album_ids, batch_id) -> list[int]`: live albums in `album_ids` get `deleted_at`, `deletion_batch_id` and `updated_at` set; returns the ids actually trashed, read before the update inside the transaction.
  - `trash_photos_of_albums(album_ids, batch_id) -> list[int]`: the same for live photos whose `album_id` is in the list.

  Extend `FakeTrashRepository` too.
- [X] T046 [US2] Add `delete_album(album_id, actor_id) -> TrashOutcome` to `GalleryTrashService`. In one transaction:
  1. `parent_map(lock=True)`;
  2. `AlbumNotFoundError` if the album is not in it;
  3. `snapshot()`;
  4. `subtree_ids`;
  5. `create_batch(ALBUM, ...)`;
  6. `trash_albums`, then `trash_photos_of_albums`;
  7. `upsert` marks for both kinds;
  8. `touch_changed(before)`.

  Log `gallery_trashed` with the album and photo counts (every row of the batch, root included). Split into helpers of 4–20 lines.
- [X] T047 [US2] Unit tests in `server/features/gallery/tests/unit/test_gallery_trash_service.py`:
  - A → B → C cascade in one batch, with marks for 3 albums and every photo;
  - a photo trashed earlier keeps its own batch and has no new mark;
  - second delete → `AlbumNotFoundError`;
  - the parent whose resolved cover came from B is touched;
  - the log counts are right.
- [X] T048 [US2] Add `delete()` to `AlbumDetailAPIView` in `server/features/gallery/views/albums.py` (`GALLERY_WRITE`; `delete_album(album_id, request.user.pk)` → `204`)
- [X] T049 [P] [US2] **Regression** invisibility tests `server/features/gallery/tests/integration/test_trash_invisibility.py` (spec US2 scenarios 1–6, FR-006–FR-011). After deleting A (A → B → C, with photos):
  - `GET /api/albums/` lacks A, B and C; `GET /api/photos/` lacks their photos;
  - `GET /api/albums/{A}/photos/` and `/{B}/photos/` → `404`;
  - parent P's `cover_url` / `cover_source_album_id` fall to the next live source or `null`;
  - every write under A answers `404`: `POST /api/albums/` with `parent_id=A`, `PATCH` moving an album or photo into B, `POST /api/photos/` into C, `PUT/DELETE /api/albums/{A}/cover/`, `PUT /api/albums/order/` with `parent_id=A`;
  - an album whose only photo is trashed gets the automatic cover on its next upload;
  - `PUT /api/albums/order/` of P's children without A succeeds, and with A it gives `400` with A in `unexpected`.
- [X] T050 [P] [US2] **Regression** name reuse in `server/features/gallery/tests/integration/test_trash_api.py`: after deleting "Culto" under P, `POST /api/albums/` `{"name": "Culto", "parent_id": P}` → `201`; the same for roots
- [X] T051 [P] [US2] Album part of `server/features/gallery/tests/integration/test_trash_api.py`: `DELETE /api/albums/{id}/` → `204`; unknown or already trashed → `404` with `album_id`; the rows of the batch share one `deletion_batch`; files untouched
- [X] T052 [P] [US2] Add rows for `DELETE /api/albums/{id}/` to `server/features/gallery/tests/integration/test_gallery_access.py` (as T044)

**Checkpoint**: Whole albums can be removed; everything under them is hidden and still restorable
in the database.

---

## Phase 5: User Story 3 - The app forgets what was deleted (Priority: P1)

**Goal**: `GET /api/gallery/changes/?since=` returns what changed and what was deleted since a
cursor, with full sync, overlap and `full_sync_required` per the contract.

**Independent Test**: Full sync; create an album, rename a photo, delete a photo and an album
with photos; delta with the cursor holds exactly those; after a purge the ids are still deleted.

### Implementation

- [X] T053 [US3] Add `ids_since(kind, since: datetime) -> list[int]` (marks with `deleted_at > since`, ordered by id) to `DeletionMarkRepository` (Protocol, impl, fake)
- [X] T054 [US3] Create `server/features/gallery/services/gallery_change_feed_service.py`, class `GalleryChangeFeedService(album_service, gallery_repository, mark_repository, clock)`, with `changes(since_raw: str | None) -> ChangeFeed` (research R-07):
  - Read `now` first; the cursor is `encode_cursor(now)`.
  - `since_raw is None` → full sync: `album_service.list_albums()`, every live photo in tree order through `order_photos_by_tree` (T055), empty deleted lists, `full_sync_required=False`.
  - Decode fails or `requires_full_sync` → empty lists, `full_sync_required=True`.
  - Otherwise, with `start = feed_window_start(since)`: albums whose `updated_at > start` from `list_albums()` (tree order kept); photos from `list_photos_changed_since(start)` tree-ordered; `ids_since(ALBUM|PHOTO, start)`.
- [X] T055 [US3] Extract the tree-order sort of `GalleryService.list_all_photos` into `server/features/gallery/services/photo_ordering.py` (`order_photos_by_tree(photos, records) -> list[PhotoView]`) and make `GalleryService` use it. Same commit as T054. Unit test in `server/features/gallery/tests/unit/test_photo_ordering.py`.
- [X] T056 [US3] Create `server/features/gallery/serializers/feed_serializers.py` (`ChangeFeedSerializer` nesting `AlbumSerializer` / `PhotoSerializer` with the request context) and `server/features/gallery/views/changes.py` (`GalleryChangesAPIView`, `permission_classes = [IsMemberUser]`, `get()` passes `request.query_params.get("since")` unparsed and answers `200`). Add the route `path("api/gallery/changes/", ...)` to `server/features/gallery/urls.py`. Register the service in `server/config/di.py` and wire `"features.gallery.views.changes"`.
- [X] T057 [US3] Unit tests in `server/features/gallery/tests/unit/test_gallery_change_feed_service.py`, using `FakeClock` and the fakes:
  - no `since` → everything, `full_sync_required: false`;
  - delta returns only rows changed after `since − 90 s`, and a row changed 91 s before `since` is not returned;
  - deleted ids per kind, cascaded photos included;
  - a restored row (mark removed, `updated_at` bumped) appears as changed and not deleted;
  - `since` 90 days old, garbage, `v2.`, or in the future → empty lists with `full_sync_required: true`;
  - the returned cursor decodes to `now`.
- [X] T058 [P] [US3] **Regression** API tests `server/features/gallery/tests/integration/test_change_feed_api.py` (spec US3 scenarios 1–11, time moved with `FakeClock` overridden in the container):
  - full sync, then delta after create, rename and delete;
  - album delete lists its sub-album and all photos;
  - rename lists the album and its photos;
  - photo reorder lists only the moved photos, with new `position`;
  - sub-album cover replace lists the ancestors;
  - **across a purge**: delete, advance 31 days, run `purge_gallery_trash` once US5 lands (until then, delete the rows through `all_objects` in the test), and a feed with a pre-delete cursor still lists the ids;
  - non-member → `403`.
- [X] T059 [P] [US3] Add the `GET /api/gallery/changes/` rows to `server/features/gallery/tests/integration/test_gallery_access.py` (every member `200`, non-member `403`, anonymous `401`)

**Checkpoint**: The Android app can sync incrementally and learn deletions.

---

## Phase 6: User Story 4 - Restore something deleted by mistake (Priority: P2)

**Goal**: An owner lists the trash as one entry per batch and restores an album or photo root,
bringing back exactly its batch, refusing name conflicts and trashed parents.

**Independent Test**: Trash P1, then delete A (B, P2, P3); the trash shows A (1 sub-album,
2 photos) and P1; restore A → A, B, P2, P3 live in their positions, P1 still trashed.

### Implementation

- [X] T060 [US4] Add to `TrashRepository` (Protocol, impl, fake):
  - `batch_rooted_at(kind, root_id) -> TrashedRoot | None`: a small DTO in `trash_dtos.py` with `batch_id`, `kind`, `root_id`, `name`, `parent_album_id`, read through `all_objects`.
  - `restore_batch(batch_id) -> TrashOutcome`: every row of the batch gets `deleted_at=NULL`, `deletion_batch=NULL`, `updated_at=now`, and the batch row is deleted. It returns the ids it restored.
  - `list_entries() -> list[TrashEntryRow]`: research R-13. One batch query with `select_related("deleted_by")` and two `Subquery` counts, plus one root-album query and one root-photo query (`select_related("uploaded_by")`). Four queries in total. The display name is `get_full_name() or username`, `None` for a null user.
- [X] T061 [US4] Add `remove(kind, ids)` to `DeletionMarkRepository` (Protocol, impl, fake)
- [X] T062 [US4] Add to `GalleryTrashService`:
  - `list_trash() -> list[TrashEntry]` maps rows, `purge_on` from T006 and `thumbnail_path` via `file_storage.url`.
  - `restore_album(album_id) -> AlbumView` and `restore_photo(photo_id) -> PhotoView` run in one transaction with the album table locked:
    1. `batch_rooted_at`, else `TrashEntryNotFoundError`;
    2. parent live, else `TrashedParentError`;
    3. albums only: `live_sibling_named`, else `AlbumRestoreNameConflictError`;
    4. `snapshot()`;
    5. `restore_batch`;
    6. `remove` the marks for both kinds;
    7. `touch_changed(before, also=restored album ids)`.

  Translate an `IntegrityError` on the name constraints into `AlbumRestoreNameConflictError`, looking up the sibling id after the rollback. Log `gallery_restored`. Return the view from `AlbumService.view_of` / `GalleryService`'s photo read.
- [X] T063 [US4] Unit tests in `server/features/gallery/tests/unit/test_gallery_trash_service.py`:
  - exact batch restore (P1 stays trashed), positions untouched;
  - restoring B while A is trashed → `TrashEntryNotFoundError`;
  - restoring P1 while A is trashed → `TrashedParentError(photo, P1, A)`, then restoring A and P1 succeeds;
  - name conflict → `AlbumRestoreNameConflictError` with the sibling id, then succeeds after a rename;
  - marks removed and rows touched;
  - live or unknown id → `TrashEntryNotFoundError`;
  - the trash lists two entries with the right counts, names, `purge_on` and display names.
- [X] T064 [US4] Create `server/features/gallery/serializers/trash_serializers.py` (`TrashEntrySerializer`: fields per the contract, `thumbnail_url` via `absolute_media_url`) and `server/features/gallery/views/trash.py`: `TrashListAPIView` (GET), `AlbumRestoreAPIView` and `PhotoRestoreAPIView` (POST, answer `200` with `AlbumSerializer` / `PhotoSerializer`). All use `permission_classes = [IsAuthenticated, scope_permission(Scope.GALLERY, {"GET": Level.OWNER, "POST": Level.OWNER})]` (research R-11). Add the three routes to `server/features/gallery/urls.py` and wire `"features.gallery.views.trash"` in `server/config/di.py`.
- [X] T065 [P] [US4] **Regression** API tests in `server/features/gallery/tests/integration/test_trash_api.py` (restore part, spec US4 scenarios 1–8):
  - the trash body matches the contract;
  - the exact batch restore and its positions;
  - `404` for a live, a cascaded member and a purged id;
  - `400` bodies for the name conflict and the trashed parent, each with its extra keys and a Portuguese `detail`;
  - the restored album is back under its parent and can be a cover source again;
  - `thumbnail_url` from the listing is served to the owner by the media route.
- [X] T066 [P] [US4] Add the trash and restore rows to `server/features/gallery/tests/integration/test_gallery_access.py`: Admin, Liderança and Mídia are allowed; a member without a role gets `403` before existence; anonymous gets `401`

**Checkpoint**: Mistaken deletions can be undone within 30 days.

---

## Phase 7: User Story 5 - The trash empties itself after 30 days (Priority: P2)

**Goal**: `purge_gallery_trash` deletes batches older than 30 days (rows, then files after
commit, descendants first), keeps going past a failing batch, reports, and expires marks older
than 90 days.

**Independent Test**: Trash a tree and a single photo, age them 31 days, run twice: first run
purges rows and files, second changes nothing, feed still lists the ids.

### Implementation

- [X] T067 [US5] Add to `TrashRepository` (Protocol, impl, fake):
  - `expired_batch_ids(before) -> list[UUID]`, oldest first.
  - `purge_batch(batch_id) -> PurgedBatch`: a DTO with `album_ids`, `photo_ids` and `file_names`. It collects the non-empty `image`, `thumbnail` and `cover_image` of its rows through `all_objects`, deletes photos, then albums in `purge_order` using the batch albums' parent map, then the batch row. Rows only; the caller owns the transaction.
- [X] T068 [US5] Add `expire(before) -> int` to `DeletionMarkRepository` (Protocol, impl, fake)
- [X] T069 [US5] Create `server/features/gallery/services/gallery_purge_service.py`, class `GalleryPurgeService(trash_repository, mark_repository, file_storage, clock)`, with `purge_expired() -> PurgeReport` (research R-09):
  - For each id from `expired_batch_ids(now - TRASH_RETENTION)`, open its own `transaction.atomic()`, call `purge_batch`, and schedule `file_storage.delete` for each name with `transaction.on_commit(..., robust=True)`.
  - On any exception: roll back that batch, log `gallery_purge_skipped` (batch, exception type), record the skip and continue.
  - Log `gallery_purged` per batch (`actor_id: null`).
  - Then `expire(now - MARK_RETENTION)`, and log `gallery_purge_summary`.
- [X] T070 [US5] Create `server/features/gallery/management/commands/purge_gallery_trash.py` (pattern of `generate_photo_thumbnails.py`): an `@inject` module-level `_purge()` and `summary_line(report) -> str` per the contract. It exits `0` even with skips. Register `gallery_purge_service` and wire the command module in `server/config/di.py`.
- [X] T071 [US5] Unit tests in `server/features/gallery/tests/unit/test_gallery_purge_service.py` (fakes, `FakeClock`):
  - only batches older than 30 days are purged;
  - a failing batch is skipped and the next still purged;
  - files are deleted only for committed batches;
  - marks are untouched by row purges and expired after 90 days;
  - a second run purges nothing;
  - `summary_line` formats the counts.
- [X] T072 [P] [US5] **Regression** integration test `server/features/gallery/tests/integration/test_purge_gallery_trash.py` (temporary `MEDIA_ROOT`, real files, `call_command`):
  - A → B → C with photos, aged 31 days, purged despite `PROTECT`; the rows and every file are gone;
  - a photo whose file is already missing → purged, no error;
  - a batch under 30 days → untouched;
  - a forced `ProtectedError`: an older photo batch whose rows remain because its purge was made to fail, which leaves the album batch skipped, reported, and retried successfully the next run;
  - a second run prints `purged 0 batches`;
  - marks still present after the purge.

**Checkpoint**: The trash is self-cleaning once the host cron is set up.

---

## Phase 8: User Story 6 - The Django admin cannot bypass the trash (Priority: P3)

**Goal**: The admin offers no delete for albums or photos, and never lists trashed albums.

**Independent Test**: No delete button or bulk action on either admin; a POST to the delete URL
is refused; trashed albums are absent from the changelist, the parent field and the upload page.

### Implementation

- [X] T073 [US6] In `server/features/gallery/admin.py`, add `has_delete_permission(self, request, obj=None) -> bool: return False` to `AlbumAdmin` and `PhotoAdmin`, with a comment citing spec FR-012 (deletion lives in the app, which records it and reports it to devices)
- [X] T074 [P] [US6] Admin tests in `server/features/gallery/tests/integration/test_gallery_admin.py`: the change pages have no delete link; the changelist actions omit `delete_selected`; GET/POST `admin:gallery_album_delete` → `403`; a trashed album is absent from the album changelist, from the `parent` choices of the album form and from the upload page's album list

**Checkpoint**: No path deletes a gallery row outside the trash and the purge.

---

## Phase 9: Polish & Cross-Cutting Concerns

- [X] T075 [P] Add the new endpoints to `server/core/tests/integration/test_management_access_matrix.py` (gallery rows: `DELETE` albums/photos `owner`; trash `GET` and restore `POST` `owner` override) and keep the scope-matrix assertions green
- [X] T076 [P] Update the module docstrings and comments touched by this feature:
  - `server/features/gallery/repositories/gallery_file_storage.py`: files of trashed rows are hidden by the media check, and removed by the purge.
  - `server/features/media/services/media_access_service.py`: the class docstring gains the trash step and points to spec 014.
  - `server/features/media/domain/media_rules.py`: the `FOLDER_RULES` comment for `gallery`.
- [X] T077 Confirm `server/core/domain/exceptions.py`, `server/features/gallery/services/gallery_trash_service.py` and every new file are under 500 lines, and every function is 4–20 lines. Split `gallery_trash_service.py` into delete and restore modules if it grows past the limit.
- [X] T078 Run `pytest`, `mypy .`, `ruff check .`, `black --check .`, `bandit -r .` and `python manage.py makemigrations --check --dry-run` from `server/`; all green
- [ ] T079 Run the quickstart validation (`specs/014-gallery-trash-sync/quickstart.md` §1–§5), including §3 against a restored production dump with the real rollback to `gallery 0003`, and §3 step 6 `EXPLAIN` showing the partial indexes used
- [X] T080 Mark the tasks of `specs/gallery/tasks.md` done by this feature and record the host cron entry (quickstart §6) in the deploy notes handed to the operator

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies. T002–T005 are committed with the first code commit
  of Phase 2.
- **Foundational (Phase 2)**: depends on Setup and blocks every story. Inside it: T014 →
  T015 → T016; T019 + T020 + T021 + T022 form one commit; T026 → T027.
- **US1 (Phase 3)**: after Phase 2. T037–T040 form one commit, the media port.
- **US2 (Phase 4)**: after US1, since it extends `GalleryTrashService` and `TrashRepository`
  created there.
- **US3 (Phase 5)**: after Phase 2 for changes; its deletion assertions need US1/US2 deletes.
  It can be built in parallel with US2 and fully tested once US2 lands.
- **US4 (Phase 6)**: after US2, because restore needs album batches.
- **US5 (Phase 7)**: after US2. T058's across-the-purge case switches to the command once T070
  exists.
- **US6 (Phase 8)**: after Phase 2 only.
- **Polish (Phase 9)**: after the desired stories.

### Within Each Story

Protocols → implementations and fakes → service → view/command → tests (unit before
integration). Every commit type-correct.

### Parallel Opportunities

- Phase 1: T003, T004 and T005 alongside T002.
- Phase 2: the domain pairs T006/T007, T008/T009, T010/T011 and T012/T013 are all [P]. Then T017,
  T018, T023 and T025 after their prerequisites.
- US1: T031 alongside T030; the tests T041–T044 in parallel once the code is in.
- US6 can run in parallel with any story after Phase 2.

---

## Parallel Example: Foundational domain

```text
Task: "Create trash_rules.py in server/features/gallery/domain/trash_rules.py"      (T006)
Task: "Create feed_cursor.py in server/features/gallery/domain/feed_cursor.py"      (T008)
Task: "Add changed_cover_albums to server/features/gallery/domain/album_tree.py"    (T010)
Task: "Add trash exceptions to server/core/domain/exceptions.py"                    (T012)
```

## Parallel Example: User Story 1 tests

```text
Task: "Media service unit cases in server/features/media/tests/unit/test_media_access_service.py" (T041)
Task: "Trashed gallery files regression in server/features/gallery/tests/integration/test_media_trashed_gallery_files.py" (T042)
Task: "Photo delete API tests in server/features/gallery/tests/integration/test_trash_api.py" (T043)
Task: "Access rows in server/features/gallery/tests/integration/test_gallery_access.py" (T044)
```

---

## Implementation Strategy

### MVP First (User Story 1)

1. Phase 1 + Phase 2. Every read now ignores trashed rows; nothing trashes yet.
2. Phase 3 (US1): photos can be deleted and their files stop being served.
3. **STOP and VALIDATE**: quickstart §4 steps 1–5 for a single photo.

### Incremental Delivery

1. US1 → a mistaken photo is gone and undownloadable (MVP).
2. US2 → whole albums.
3. US3 → devices drop deleted photos on their next sync.
4. US4 → restore within 30 days.
5. US5 → the purge; then set up the host cron (quickstart §6).
6. US6 → admin closed. It can land any time after Phase 2.

Deploying before US5 is safe: nothing is purged, so everything stays restorable.

---

## Notes

- [P] tasks touch different files and depend on no incomplete task.
- Log lines carry ids only (research R-14); never names, captions or paths.
- Do not hand-edit `0004`; if `makemigrations` output differs from T016's list, revisit the model
  change rather than the migration.
- Commit after each logical group, keeping the whole tree type-correct.
