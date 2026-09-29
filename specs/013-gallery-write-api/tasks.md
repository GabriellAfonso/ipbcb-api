---

description: "Task list for Gallery Write API"
---

# Tasks: Gallery Write API

**Input**: Design documents from `specs/013-gallery-write-api/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/gallery-api.md,
quickstart.md

**Tests**: Included. CLAUDE.md §10 requires a test for every new function, and the request asks
for regression tests for the cycle check and root-level uniqueness. Fakes are named classes in
`server/features/gallery/tests/fakes.py`, never inline stubs.

**Organization**: Tasks are grouped by user story (US1–US7 from spec.md). Paths are relative to
the repository root. Run commands from `server/` with `.venv_windows` active (PowerShell).

**Commit rule**: the mypy pre-commit hook checks the whole tree, so every commit must leave it
type-correct. Tasks that must land in the same commit say so. Spec and code go together
(CLAUDE.md §6.2): Phase 1 docs are committed with the first code commit of Phase 2.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1–US7 from spec.md

---

## Phase 1: Setup

**Purpose**: Known-green baseline, and specs updated to the target state before any code.

- [X] T001 Run `pytest` and `mypy .` from `server/` on branch `013-gallery-write-api` and confirm both pass before any change
- [X] T002 Rewrite `specs/gallery/spec.md` to the state this feature produces (spec FR-021): Album model (`name` unique among siblings with roots included, `parent` PROTECT, `description`, `event_date`, `position`, `cover_image`), Photo model (`position`, `thumbnail`, `uploaded_by` never serialized, new path `gallery/{album_id}/{uuid}.{ext}`, old files keep theirs), every endpoint and body from `specs/013-gallery-write-api/contracts/gallery-api.md` with its permission ("member" or level on `gallery`), cover resolution and tree order rules, derivative sizes, 50 MP limit, upload status table (201/207/canonical 400 with `rejected`), `GET /api/albums/{id}/photos/` 404, and the permission statement "Admin, Liderança and Mídia hold `owner` on `gallery`" replacing "Liderança and Mídia `manage`"; keep the media access paragraph (spec 009) and the admin upload section, now stating it goes through the same service
- [X] T003 [P] Rewrite `specs/gallery/plan.md` (drop the stale "No service/repository layer" decision; list the decisions of `specs/013-gallery-write-api/plan.md` D-1…D-12 by reference) and `specs/gallery/tasks.md` (only what stays missing after 013: deletion and trash → 014, tagging → 015)
- [X] T004 [P] Amend `specs/012-feature-role-permissions/spec.md` (spec FR-020): scope matrix row `gallery` → Liderança `owner`, Mídia `owner`; replace the `gallery` future-feature note with "gallery write endpoints: `specs/013-gallery-write-api/`"; FR-009 → "The Leader role MUST NOT hold `owner` on any scope except `gallery` (feature 013)"; SC-002 and User Story 2 ("Nothing they do can delete data") scoped to "outside `gallery`"; edge case "Leader + Media on `gallery` is `manage`" → pick another scope (`events`); Out of Scope drop "Gallery write endpoints"

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Exceptions, pure domain rules, schema and data migrations, image processing, file
storage, DTOs, fakes and the permission helper. No endpoint yet.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

### Domain

- [X] T005 [P] Add to `server/core/domain/exceptions.py` (research R-09): `AlbumNotFoundError(album_id)` and `PhotoNotFoundError(photo_id)` (subclass `NotFoundError`, English message with the id); `AlbumCycleError(album_id, parent_id, chain: list[int])` (subclass `ValidationError`, Portuguese message "Não é possível mover o álbum {album_id} para dentro do álbum {parent_id}: {parent_id} está dentro de {album_id}.", `extra_context()` → `album_id`, `parent_id`, `chain`); `DuplicateAlbumNameError(name, parent_id)` (`ValidationError`, Portuguese "Já existe um álbum chamado '{name}' neste local."); `OrderMismatchError(missing, unexpected, repeated)` (`ValidationError`, English "Order must list every sibling exactly once: missing […], unexpected […], repeated […].", `extra_context()` with the three lists); `NoPhotoAcceptedError(rejected: list[dict[str, str]])` (`ValidationError`, detail "Nenhuma imagem foi aceita.", `extra_context()` → `{"rejected": rejected}`); `ImageProcessingError(filename)` (`ValidationError`, Portuguese "Não foi possível processar a imagem. Envie outro arquivo."); plus `ImageTooLargeError(width, height, max_pixels)` (`ValidationError`, Portuguese message with the dimensions and the 50 MP limit). Docstring with example on each
- [X] T006 [P] Test T005 in `server/core/tests/unit/test_gallery_exceptions.py`: message contains the offending values; `custom_exception_handler` maps each to 404/400 with `error_code` and merges `extra_context()` (the `rejected` list reaches the body of `NoPhotoAcceptedError`)
- [X] T007 [P] Create `server/features/gallery/domain/album_tree.py` (research R-02, R-06): frozen dataclass `AlbumNode(id, parent_id, position, has_own_cover)`; `find_cycle(album_id, new_parent_id, parent_of: Mapping[int, int | None]) -> list[int] | None` (walk up from `new_parent_id`; returns the chain from `new_parent_id` to `album_id` when reached, `[album_id]` when `new_parent_id == album_id`, `None` for `None` parent; stops on a repeat); `tree_order(nodes) -> list[int]` (pre-order DFS, children by `(position, id)`, visited set; albums whose parent is missing or unreachable because of a cycle are appended at the end by `(position, id)` so no album disappears); `resolve_cover_sources(nodes) -> dict[int, int | None]` (memoized post-order: own cover → self; else first child by `(position, id)` with a non-`None` source; visited set)
- [X] T008 [P] Test T007 in `server/features/gallery/tests/unit/test_album_tree.py`: **regressions** move under self and under grandchild return the chain; moving to root returns `None`; tree order with interleaved positions; cover taken depth-first (spec US3 scenario 3: "Retiros" → "Sábado", not "2025"); album with no cover below → `None`; a cycle in the input (A→B→A) terminates for all three functions and every album still appears in `tree_order`
- [X] T009 [P] Create `server/features/gallery/domain/gallery_rules.py`: `normalize_album_name(raw) -> str` (strip; blank raises `ValidationError` in Portuguese "O nome do álbum não pode ficar vazio."); `fit_photo_name(filename, max_length=100) -> str` (cut the stem keeping the extension); `compare_order_ids(requested: Sequence[int], current: Collection[int]) -> OrderDiff` (frozen dataclass `missing`, `unexpected`, `repeated`, sorted; `is_exact` property)
- [X] T010 [P] Test T009 in `server/features/gallery/tests/unit/test_gallery_rules.py`: whitespace, blank, long name keeps `.jpg`, name without extension, order exact / missing / unexpected / repeated / empty-empty

### Schema and migrations

- [X] T011 Change `server/features/gallery/models/gallery.py` per `specs/013-gallery-write-api/data-model.md`: `Album.name` without `unique`; `parent` FK self `null=True, blank=True, on_delete=PROTECT, related_name="children"`; `description` TextField blank default ""; `event_date` DateField null blank; `position` PositiveIntegerField default 0; `cover_image` ImageField blank (upload_to returning `gallery/covers/{id}/{uuid hex}.jpg`); `Meta` with `ordering = ["position", "id"]`, verbose names, the two conditional `UniqueConstraint`s (`unique_album_name_per_parent`, `unique_root_album_name`), index on `(parent, position)`. `Photo`: `thumbnail` ImageField blank; `uploaded_by` FK `settings.AUTH_USER_MODEL` null blank `SET_NULL` `related_name="+"`; `position`; `Meta` ordering, verbose names, index `(album, position)`. Keep `photo_upload_path` importable (referenced by `0001_initial`), now returning `gallery/{album_id}/{uuid hex}.{ext}` with a comment saying why it stays
- [X] T012 Run `python manage.py makemigrations gallery` → `server/features/gallery/migrations/0002_*.py`; review it (AlterField on `name`, AddField ×8, AddConstraint ×2, AddIndex ×2, AlterModelOptions) and do not hand-edit it
- [X] T013 Hand-write data migration `server/features/gallery/migrations/0003_backfill_positions.py` with the reason at the top (positions added by 0002 are all 0; reads now order by position; roots numbered by `name`, photos per album by `(uploaded_at, id)`; reverse is a no-op because 0001's schema ignores positions; "Verified against a restored production dump: pending (T071)"). Use `apps.get_model`, `bulk_update`, no application imports
- [X] T014 [P] **Regression** test in `server/features/gallery/tests/integration/test_album_constraints.py`: two roots with the same name raise `IntegrityError`; same name under two different parents is allowed; same name twice under one parent raises; `Album.full_clean()` reports the root duplicate (the admin path); deleting an album with a child raises `ProtectedError`
- [X] T015 [P] Test T013 in `server/features/gallery/tests/integration/test_position_backfill_migration.py` with `MigrationExecutor` (pattern of `server/features/accounts/tests/integration/test_is_admin_conversion_migration.py`): albums "C", "A", "B" and photos uploaded out of id order get positions by name / by `uploaded_at`; migrating back to 0001 and forward again succeeds
- [X] T016 Hand-write `server/core/migrations/0006_gallery_owner_for_leader_media.py` (research R-10) with the reason at the top (requester raised Liderança and Mídia to `owner` on `gallery` in feature 013 so `DELETE …/cover/` and feature 014 work; levels live in the groups; 0005 is applied in production and cannot change; permission rows get-or-created because `post_migrate` runs later; reverse swaps back; "Verified against a restored production dump: pending (T071)"). Forward: for `leader` and `media`, add `gallery__owner`, remove `gallery__manage`. Depends on `("core", "0005_seed_panel_roles")`
- [X] T017 Test T016 in `server/core/tests/integration/test_gallery_owner_migration.py` (forward: both groups hold `gallery__owner`, not `gallery__manage`, other permissions untouched; backward: the opposite) and update the gallery expectations in `server/core/tests/integration/test_panel_roles_seed.py` and the `gallery` row of `server/core/tests/integration/test_management_access_matrix.py` to `owner` — same commit as T016

### Image processing and storage

- [X] T018 [P] Create `server/features/gallery/imaging/__init__.py` and `server/features/gallery/imaging/interfaces.py` with the `ImageProcessor` Protocol (research R-04): `dimensions(source: IO[bytes]) -> tuple[int, int]` (header only), `bounded_jpeg(source, longest_side: int, quality: int) -> bytes`, `square_jpeg(source, side: int, quality: int) -> bytes`, `capture_date(source) -> date | None`; contract: raise `ImageProcessingError` on any decode failure, always leave the stream rewound
- [X] T019 [P] Create `server/features/gallery/imaging/pillow_image_processor.py` — `PillowImageProcessor`, the only derivative code importing Pillow: open → `seek(0)` frame for GIF → `draft("RGB", …)` → `ImageOps.exif_transpose` → alpha composited on white → `ImageOps.fit(…, centering=(0.5, 0.5))` or `thumbnail` (never upscale) → `save(format="JPEG", quality=…, optimize=True)`; `capture_date` from `DateTimeOriginal` in the Exif IFD, fallback `DateTime`, `None` on anything malformed; `DecompressionBombError`, `UnidentifiedImageError`, `OSError`, `ValueError` → `ImageProcessingError`
- [X] T020 [P] Test T019 in `server/features/gallery/tests/integration/test_pillow_image_processor.py` with images generated in memory: 3000×2000 → bounded 1000×667; 800×600 stays 800×600; any input → square 1000×1000 (and a 500×300 upscaled to 1000×1000 for the cover); RGBA PNG → white background JPEG; animated GIF → first frame; EXIF orientation 6 → rotated output; EXIF `DateTimeOriginal` → date; malformed date → `None`; truncated bytes → `ImageProcessingError`; stream rewound after each call
- [X] T021 [P] Add `GalleryFileStorage` Protocol to `server/features/gallery/repositories/interfaces.py` and `DefaultStorageGalleryFileStorage` in `server/features/gallery/repositories/gallery_file_storage.py` (research R-05): `save_original(album_id, extension, stream) -> str`, `save_thumbnail(album_id, content: bytes) -> str`, `save_cover(album_id, content: bytes) -> str`, `open(name) -> IO[bytes]`, `delete(name)`, `url(name) -> str`; names `gallery/{album_id}/…`, `gallery/thumbs/{album_id}/…`, `gallery/covers/{album_id}/…` with `uuid4().hex`
- [X] T022 [P] Test T021 in `server/features/gallery/tests/integration/test_gallery_file_storage.py` against a temporary `MEDIA_ROOT` (`settings` fixture + `tmp_path`): each save lands under the expected prefix with a 32-hex name and the given extension; `open` reads back; `delete` removes; `url` starts with `/ipbcb/media/gallery/`

### DTOs, fakes, permissions, DI

- [X] T023 [P] Add to `server/features/gallery/dtos/gallery_dtos.py` (data-model.md): `AlbumView`, `AlbumCreate`, `AlbumChanges`, `SiblingOrder`, `PhotoView`, `PhotoChanges`, `RejectedFile`, `ThumbnailBackfillReport` (all `StrictBaseModel`); leave `UploadResult` as is until T031
- [X] T024 [P] Create `server/features/gallery/views/permissions.py` with `member_read_gallery_write_permissions(method: str) -> list[BasePermission]` (research R-07: `GET`/`HEAD`/`OPTIONS` → `[IsMemberUser()]`, otherwise `[IsAuthenticated(), scope_permission(Scope.GALLERY)()]`) and test it in `server/features/gallery/tests/unit/test_gallery_view_permissions.py`
- [X] T025 Create `server/features/gallery/tests/fakes.py` with `FakeImageProcessor` (configurable dimensions, EXIF date, failure on a given filename; returns fixed bytes and records calls) and `FakeGalleryFileStorage` (in-memory dict, predictable names, records deletes); fakes for the repositories are added by the story that introduces each method
- [X] T026 Register `image_processor = providers.Singleton(PillowImageProcessor)` and `gallery_file_storage = providers.Factory(DefaultStorageGalleryFileStorage)` in `server/config/di.py`

**Checkpoint**: migrations apply on a fresh database and on the dump; domain, imaging and storage tested; no API change yet.

---

## Phase 3: User Story 1 - Upload photos from the app (Priority: P1) 🎯 MVP

**Goal**: `POST /api/photos/` stores validated photos with thumbnail, EXIF date, position and uploader; the admin upload page uses the same path; photo reads gain `thumbnail_url`.

**Independent Test**: As Mídia, upload a JPEG, a PNG and a text file renamed `.jpg` into an existing album → `207`, two accepted with thumbnails, one rejected; a member lists the album and sees both in upload order.

### Implementation

- [X] T027 [US1] Extend `GalleryRepository` Protocol (`server/features/gallery/repositories/interfaces.py`) and `server/features/gallery/repositories/gallery_repository.py`: `album_exists(album_id)`; `create_photo(album_id, image_name, thumbnail_name, name, date_taken, uploader_id) -> PhotoView` inside `transaction.atomic()`, locking the album row (`select_for_update`) and setting `position = max + 1`; `list_all_photos() -> list[PhotoView]` and `list_photos_by_album(album_id) -> list[PhotoView]` ordered by `position, id` with `select_related("album")`; a private `_to_view(photo)` mapping with `image_path` / `thumbnail_path` from `field.url` (`None` when empty). Remove `create_photo(album, image, name)` and `get_album_by_id`
- [X] T028 [US1] Add `FakeGalleryRepository` to `server/features/gallery/tests/fakes.py` and integration-test T027 in `server/features/gallery/tests/unit/test_gallery_repository.py` (move it to `tests/integration/` if it hits the DB): appended positions 0, 1, 2; `uploaded_by` stored; views carry paths; empty thumbnail → `None`
- [X] T029 [US1] Change `UploadResult` in `server/features/gallery/dtos/gallery_dtos.py` to `accepted: list[PhotoView]`, `rejected: list[RejectedFile]`, keeping `has_errors`
- [X] T030 [US1] Extend `GalleryService` in `server/features/gallery/services/gallery_service.py`: constructor takes `GalleryRepository`, `GalleryFileStorage`, `ImageProcessor`; constants `THUMBNAIL_LONGEST_SIDE_PX = 1000`, `DERIVATIVE_JPEG_QUALITY = 85`, `MAX_UPLOAD_PIXELS = 50_000_000`; `upload_photos(album_id, files, uploader_id) -> UploadResult` keeps the existing per-file `detect_image_extension` loop untouched and, per accepted file, calls a private `_store_one(...)`: pixel limit (`ImageTooLargeError`), `bounded_jpeg`, `capture_date`, `save_original`, `save_thumbnail`, `create_photo` with `fit_photo_name`; on any exception after a file was written, delete what was written and re-raise for domain errors / record as rejected with the exception message; raise `AlbumNotFoundError` before touching any file; raise `NoPhotoAcceptedError` when `accepted` is empty. Photo reads return `list[PhotoView]`; `list_photos_by_album` raises `AlbumNotFoundError` for an unknown album. Each helper 4–20 lines
- [X] T031 [US1] Update the admin upload page `server/features/gallery/views/upload.py` for the new result — same commit as T029–T030: pass `request.user.pk` as uploader; render `"{filename}: {reason}"` per rejected file; catch `NoPhotoAcceptedError` and render its `rejected`; catch `AlbumNotFoundError` instead of `NotFoundError`; update `server/features/gallery/tests/unit/test_upload.py` and `test_build_upload_html.py`
- [X] T032 [US1] Update `GalleryService` provider in `server/config/di.py` with the new dependencies — same commit as T030
- [X] T033 [US1] Unit-test the upload in `server/features/gallery/tests/unit/test_gallery_service.py` with the fakes: all accepted; partial (bad format kept as rejected with the `image_validation` message); every file rejected → `NoPhotoAcceptedError` carrying all reasons; > 50 MP rejected before any derivative is made; thumbnail failure rejected and no file or row left; EXIF date copied; long filename cut; unknown album → `AlbumNotFoundError` and no storage call; repository failure after storage writes → both files deleted
- [X] T034 [US1] Replace `PhotoListSerializer` in `server/features/gallery/serializers/serializers.py` with `PhotoSerializer` (plain `Serializer` over `PhotoView`: existing fields in the same order plus `thumbnail_url`; `image_url` / `thumbnail_url` via `request.build_absolute_uri(path)`, `None` without path or request) and add `RejectedFileSerializer`; update `server/features/gallery/tests/unit/test_serializers.py`
- [X] T035 [US1] In `server/features/gallery/views/gallery.py`: `PhotoListAPIView` gets `get_permissions()` from T024, `parser_classes` with JSON + multipart, and `post()` (`require_int(request.data.get("album_id"), "album_id")`, `request.FILES.getlist("image")`, empty list → `ValidationError` in Portuguese "Envie ao menos uma imagem no campo 'image'."; `201` when `rejected` is empty, else `207`); both GET views use `PhotoSerializer`; update `server/features/gallery/tests/unit/test_views.py`
- [X] T036 [P] [US1] Integration tests in `server/features/gallery/tests/integration/test_photo_api.py` (temporary `MEDIA_ROOT`, real Pillow): spec US1 scenarios 1–7 — bodies per contract (201, 207, canonical 400 with `rejected`, 400 without `album_id`, 404 unknown album), `name` = filename, `thumbnail_url` served under `gallery/thumbs/`, EXIF date, last position
- [X] T037 [P] [US1] Legacy-read test `server/features/gallery/tests/integration/test_gallery_legacy_reads.py` (quickstart §2): `GET /api/photos/` and `GET /api/albums/{id}/photos/` keep all previous keys, add only `thumbnail_url`; photo with an old-style path still has its URL; unknown album → 404; existing empty album → `200 []`
- [X] T038 [P] [US1] Create `server/features/gallery/tests/integration/test_gallery_access.py` with a parametrized table (Admin, Liderança, Mídia, member without role, authenticated non-member, anonymous) × endpoint-method, starting with `GET /api/photos/`, `GET /api/albums/{id}/photos/`, `POST /api/photos/`; each later story adds its rows
- [X] T039 [US1] Admin upload integration test in `server/features/gallery/tests/integration/test_gallery_admin.py`: POST to `admin:gallery_upload` as a staff user stores `gallery/{album_id}/…`, a thumbnail, position and `uploaded_by` (spec US1 scenario 9)

**Checkpoint**: the app can upload; members get thumbnails. MVP deliverable.

---

## Phase 4: User Story 2 - Build the album tree (Priority: P1)

**Goal**: create, rename, move albums with sibling-unique names and no cycles, from the API and the Django admin.

**Independent Test**: create root → child → grandchild; rename; move the grandchild to root; moving the root under its grandchild → `400`.

### Implementation

- [X] T040 [US2] Create `AlbumRepository` Protocol in `server/features/gallery/repositories/interfaces.py` and `server/features/gallery/repositories/album_repository.py`: `exists(album_id)`; `get_fields(album_id)` (name, parent_id); `sibling_name_taken(name, parent_id, exclude_id)`; `parent_map(lock: bool) -> dict[int, int | None]` (one query; `select_for_update` when `lock`); `list_nodes() -> list[AlbumNodeRow]` (id, name, parent_id, description, event_date, position, cover name) in one query; `create(AlbumCreate, position) -> int`; `update(album_id, fields: Mapping[str, object])`; `next_position(parent_id)` (lock parent row when not `None`); every write translates `IntegrityError` from the two constraints into `DuplicateAlbumNameError`
- [X] T041 [US2] Add `FakeAlbumRepository` to `server/features/gallery/tests/fakes.py` and integration-test T040 in `server/features/gallery/tests/integration/test_album_repository.py` (IntegrityError translation for root and child duplicates; `parent_map` shape; positions)
- [X] T042 [US2] Create `AlbumService` in `server/features/gallery/services/album_service.py` (depends on `AlbumRepository`, `GalleryFileStorage`): `create(AlbumCreate) -> AlbumView` (normalize name, parent exists else `AlbumNotFoundError`, duplicate pre-check, append position); `update(album_id, AlbumChanges) -> AlbumView` inside `transaction.atomic()` (unknown album / parent → `AlbumNotFoundError`; parent change → `parent_map(lock=True)` + `find_cycle` → `AlbumCycleError`, then new position at the end; same parent keeps position; name change → duplicate check against the target parent); `validate_placement(album_id | None, name, parent_id)` for the admin; `view_of(album_id)` and private `_build_views(rows)` using `resolve_cover_sources` and `storage.url`. Register `album_repository` and `album_service` in `server/config/di.py`
- [X] T043 [US2] Unit-test `AlbumService` in `server/features/gallery/tests/unit/test_album_service.py` with the fakes: create root/child, blank name, unknown parent, duplicate root (**regression**), duplicate child, same name in other parent allowed, rename, move to root, **regression** move under self and under descendant (message names both ids, nothing changed), move appends, same-parent PATCH keeps position, `event_date` null clears
- [X] T044 [US2] Create `server/features/gallery/serializers/album_serializers.py`: `AlbumSerializer` (output over `AlbumView`, `cover_url` absolute), `AlbumCreateSerializer` (`name` max 100, `parent_id` nullable, `description`, `event_date` nullable), `AlbumUpdateSerializer` (all optional, `partial=True`; the view builds `AlbumChanges` from `validated_data` keys only)
- [X] T045 [US2] Create `server/features/gallery/views/albums.py`: `AlbumListCreateAPIView` (permissions via T024; `post()` → `201`) and `AlbumDetailAPIView` (`[IsAuthenticated, scope_permission(Scope.GALLERY)]`, `patch()` → `200`, `require_object_body` first); add `api/albums/` and `api/albums/<int:album_id>/` to `server/features/gallery/urls.py`; add the module to the DI wiring list
- [X] T046 [P] [US2] Integration tests in `server/features/gallery/tests/integration/test_album_api.py`: spec US2 scenarios 1–9, including the **regression** cycle cases with the contract body (`album_id`, `parent_id`, `chain`) and a file-path check that rename/move leave photo, thumbnail and cover names unchanged
- [X] T047 [US2] Add `POST /api/albums/` and `PATCH /api/albums/{id}/` rows to `server/features/gallery/tests/integration/test_gallery_access.py`
- [X] T048 [US2] Django admin in `server/features/gallery/admin.py` (research R-11): `AlbumAdminForm.clean()` calls `album_service.validate_placement` and turns domain errors into form errors; `AlbumAdmin.save_model()` calls `album_service.create/update`; `fields = ["name", "parent", "description", "event_date"]`, `readonly_fields = ["position", "cover_image"]`; keep the upload URL; add `features.gallery.admin` to the DI wiring list in `server/config/di.py`
- [X] T049 [US2] Test T048 in `server/features/gallery/tests/integration/test_gallery_admin.py` (admin form refuses duplicate root name and a cycle; save appends position; deleting an album with a child shows the protected page) and adjust `server/core/tests/test_admin_registrations.py` if it asserts the admin classes

**Checkpoint**: the app can build the tree; admin obeys the same rules.

---

## Phase 5: User Story 3 - Members browse albums with covers (Priority: P1)

**Goal**: `GET /api/albums/` returns every album, flat, in tree order, with resolved cover.

**Independent Test**: build roots and sub-albums with and without covers (fixtures set `cover_image` directly); list as a member; compare `cover_url` / `cover_source_album_id` with the rule.

### Implementation

- [X] T050 [US3] Add `AlbumService.list_albums() -> list[AlbumView]` in `server/features/gallery/services/album_service.py` (one `list_nodes()`, `tree_order`, `_build_views`) and unit-test it in `server/features/gallery/tests/unit/test_album_service.py` (tree order, empty albums present, depth-first cover, no cover → both `None`, own cover → own id)
- [X] T051 [US3] Add `get()` to `AlbumListCreateAPIView` in `server/features/gallery/views/albums.py` (member permission via T024)
- [X] T052 [P] [US3] Integration tests in `server/features/gallery/tests/integration/test_album_list_api.py`: spec US3 scenarios 1–6 (scenario 5 replaces a sub-album cover directly in the DB and re-lists); query count bounded with `django_assert_max_num_queries` for 50 albums
- [X] T053 [US3] Add `GET /api/albums/` rows to `server/features/gallery/tests/integration/test_gallery_access.py`

**Checkpoint**: the app can render the album grid from one call.

---

## Phase 6: User Story 4 - Covers set automatically and by hand (Priority: P2)

**Goal**: first upload into an empty uncovered album creates its cover; `PUT`/`DELETE …/cover/`.

**Independent Test**: upload two photos into a new album → cover from the first; replace with an unrelated image; delete; upload again → still no cover.

### Implementation

- [X] T054 [US4] Extend `AlbumRepository` (`interfaces.py`, `album_repository.py`) and `FakeAlbumRepository`: `get_cover_name(album_id)`, `set_cover_name(album_id, name | None)`, `has_photos(album_id)`
- [X] T055 [US4] Create `AlbumCoverService` in `server/features/gallery/services/album_cover_service.py` (depends on `AlbumRepository`, `GalleryFileStorage`, `ImageProcessor`; constants `COVER_SIDE_PX = 1000`, `DERIVATIVE_JPEG_QUALITY = 85`, `MAX_UPLOAD_PIXELS` shared from one module-level constant in `gallery_service.py` or a `features/gallery/domain/image_limits.py`): `replace_cover(album_id, upload)` (`AlbumNotFoundError`; `detect_image_extension`; pixel limit; `square_jpeg`; save; set in a transaction; old file deleted `on_commit`; new file deleted if the transaction fails); `remove_cover(album_id)` (no-op without a cover; file deleted `on_commit`); `cover_from_first_photo(album_id, source)` (only when no own cover and no photos; failures logged as structured JSON with `album_id`, never raised). Register in `server/config/di.py`
- [X] T056 [US4] Call `AlbumCoverService.cover_from_first_photo` from `GalleryService._store_one` in `server/features/gallery/services/gallery_service.py`, checked before the photo row is created so "no photos" is true only for the first accepted file; inject the cover service in `server/config/di.py`
- [X] T057 [US4] Unit tests in `server/features/gallery/tests/unit/test_album_cover_service.py` and `test_gallery_service.py`: replace keeps old until commit; invalid image leaves previous cover; > 50 MP rejected; remove twice is fine; auto cover only from the first accepted file of a batch; album with photos gets no auto cover; album with a removed cover and photos stays without; auto-cover failure keeps the photo accepted
- [X] T058 [US4] Create `server/features/gallery/views/album_cover.py` — `AlbumCoverAPIView` (`[IsAuthenticated, scope_permission(Scope.GALLERY)]`, multipart; `put()` field `image`, missing → `ValidationError` Portuguese, returns `200` Album via `album_service.view_of`; `delete()` → `204`); route `api/albums/<int:album_id>/cover/`; wiring
- [X] T059 [P] [US4] Integration tests in `server/features/gallery/tests/integration/test_album_cover_api.py`: spec US4 scenarios 1–7 with real files (cover is 1000×1000 JPEG under `gallery/covers/{id}/`; moving the source photo keeps the cover; delete removes the file)
- [X] T060 [US4] Add `PUT`/`DELETE …/cover/` rows to `server/features/gallery/tests/integration/test_gallery_access.py` — `DELETE` allowed for Admin, Liderança **and** Mídia (depends on T016)

**Checkpoint**: albums get covers with no effort; manual control works.

---

## Phase 7: User Story 5 - Order albums and photos by hand (Priority: P2)

**Goal**: full-list reorder of sibling albums and of an album's photos; `GET /api/photos/` in tree order.

**Independent Test**: reverse the roots and an album's photos; lists come back reversed; an order missing one id → `400`, nothing changes.

### Implementation

- [X] T061 [US5] Extend repositories and fakes: `AlbumRepository.child_ids(parent_id)` and `apply_order(ids)`; `GalleryRepository.photo_ids(album_id)` and `apply_order(ids)` — each `apply_order` one `bulk_update` of `position = index` in `transaction.atomic()`
- [X] T062 [US5] Add `AlbumService.reorder(SiblingOrder)` (unknown `parent_id` → `AlbumNotFoundError`; `compare_order_ids` → `OrderMismatchError`) and `GalleryService.reorder_photos(album_id, ids)`; change `GalleryService.list_all_photos` to sort by `tree_order` rank of the album, then position, id (needs `AlbumRepository.list_nodes`, inject it)
- [X] T063 [US5] Unit tests in `test_album_service.py` and `test_gallery_service.py`: exact order applied; missing / unexpected / foreign-parent / nonexistent / repeated ids → `OrderMismatchError` with lists and no write; empty album `[]` ok; photo list in tree order
- [X] T064 [US5] Views: `AlbumOrderAPIView` in `server/features/gallery/views/albums.py` (`PUT`, serializer `parent_id` nullable + `ids` list of int, → `204`) and `AlbumPhotoOrderAPIView` in `server/features/gallery/views/gallery.py` (`PUT`, `ids` → `204`); routes `api/albums/order/` and `api/albums/<int:album_id>/photos/order/` in `server/features/gallery/urls.py`
- [X] T065 [P] [US5] Integration tests in `server/features/gallery/tests/integration/test_order_api.py`: spec US5 scenarios 1–4 with the contract `400` body; plus access rows in `test_gallery_access.py`

**Checkpoint**: manual order visible in every read.

---

## Phase 8: User Story 6 - Edit photo metadata and move photos (Priority: P2)

**Goal**: `PATCH /api/photos/{id}/` for `name`, `description`, `date_taken`, `album_id`.

**Independent Test**: PATCH a description and album; the photo shows the caption, lists last in the new album, same `image_url`.

### Implementation

- [X] T066 [US6] Add `GalleryRepository.photo_exists`, `update_photo(photo_id, fields)` and `move_photo(photo_id, album_id)` (append position under the target album lock) plus fakes; `GalleryService.update_photo(photo_id, PhotoChanges) -> PhotoView` (`PhotoNotFoundError`, `AlbumNotFoundError`, same album keeps position); unit tests in `test_gallery_service.py`
- [X] T067 [US6] `PhotoUpdateSerializer` in `server/features/gallery/serializers/serializers.py` (`name` 1–100, `description`, `date_taken` nullable, `album_id`; unknown keys → `ValidationError` naming them) and `PhotoDetailAPIView` (`PATCH` → `200`) in `server/features/gallery/views/gallery.py`; route `api/photos/<int:photo_id>/`
- [X] T068 [P] [US6] Integration tests in `server/features/gallery/tests/integration/test_photo_api.py`: spec US6 scenarios 1–4; access rows in `test_gallery_access.py`

**Checkpoint**: captions and moves work.

---

## Phase 9: User Story 7 - Existing photos get thumbnails at deploy (Priority: P3)

**Goal**: idempotent `generate_photo_thumbnails` command.

**Independent Test**: photos without thumbnails; run twice; first fills all readable, second fills none.

### Implementation

- [X] T069 [US7] Add `GalleryRepository.iter_photos_without_thumbnail(batch_size)` and `set_thumbnail(photo_id, name)` plus fakes; `GalleryService.fill_missing_thumbnails() -> ThumbnailBackfillReport` (open original via storage, `bounded_jpeg`, save, set; missing file or `ImageProcessingError` → skipped id); unit tests in `test_gallery_service.py`
- [X] T070 [US7] Create `server/features/gallery/management/__init__.py`, `commands/__init__.py`, `commands/generate_photo_thumbnails.py` (resolves the service from the container, prints plain text `filled N, skipped M: ids …`) and test it in `server/features/gallery/tests/integration/test_generate_photo_thumbnails.py` (fills, idempotent, skips missing file)

**Checkpoint**: every readable photo has a thumbnail after deploy.

---

## Phase 10: Polish & Cross-Cutting Concerns

- [ ] T071 Run quickstart §3 against a restored production dump (positions, groups, unchanged `image` paths, real rollback, forward again, backfill command twice); replace "pending" with the date in the docstrings of `server/features/gallery/migrations/0003_backfill_positions.py` and `server/core/migrations/0006_gallery_owner_for_leader_media.py`
- [X] T072 [P] `PhotoAdmin` in `server/features/gallery/admin.py`: `has_add_permission` → `False`; `image`, `thumbnail`, `uploaded_by`, `position` read-only; test in `server/features/gallery/tests/integration/test_gallery_admin.py`
- [X] T073 [P] Update the comment above `_CONTENT_TYPES` in `server/features/media/domain/media_rules.py`: gallery files uploaded before feature 013 keep their original filename; later ones are `{uuid}.{ext}` with the extension from the decoded format
- [X] T074 [P] Remove anything unused after the refactor (`list_all_albums` if only the admin form used it, old `PhotoListSerializer` name, `UploadResult.created_count`), and grep for `album__name` ordering leftovers
- [X] T075 Check CLAUDE.md §8 limits on every touched file (functions 4–20 lines, files < 500 lines, max 2 indentation levels); run `black .`, `ruff check .`, `mypy .`, `bandit -r . -c pyproject.toml` from `server/`
- [ ] T076 Run quickstart §1, §2 and §4; confirm `specs/gallery/spec.md` matches the implemented behaviour and update it in the same commit if anything moved

---

## Dependencies & Execution Order

### Phase dependencies

- **Setup (Phase 1)**: none. T002–T004 are committed with the first code commit.
- **Foundational (Phase 2)**: after Setup; blocks every story. T011 → T012 → T013 → T014/T015; T016 → T017; T018 → T019 → T020; T021 → T022; T025 after T018 and T021.
- **US1 (Phase 3)**: after Phase 2. Needs no album endpoint (uses existing albums).
- **US2 (Phase 4)**: after Phase 2; independent of US1.
- **US3 (Phase 5)**: after US2 (reuses `AlbumService._build_views`, `list_nodes`).
- **US4 (Phase 6)**: after US1 (auto cover hooks into upload) and US2 (`AlbumService.view_of`).
- **US5 (Phase 7)**: after US1 (photo repository) and US2 (album repository).
- **US6 (Phase 8)**: after US1.
- **US7 (Phase 9)**: after US1.
- **Polish (Phase 10)**: after all stories.

### Same-commit groups (whole-tree mypy)

- T029 + T030 + T031 + T032 (UploadResult shape, service, admin page, DI)
- T016 + T017 (role migration and the tests pinning the old level)
- T034 + T035 (serializer rename and its views)

### Within each story

Repository → fakes → service → unit tests → serializers/views/URLs → integration tests → access rows.

---

## Parallel Opportunities

- Phase 1: T003 ∥ T004 (after T002 or alongside).
- Phase 2: T005/T006, T007/T008, T009/T010, T018–T020, T021/T022, T023, T024 all touch different files.
- After Phase 2: US1 and US2 can proceed in parallel; then US3 ∥ US6 ∥ US7; US4 and US5 after both P1 tracks.

### Parallel example: Phase 2

```text
T005 exceptions            T007 album_tree.py         T009 gallery_rules.py
T018 imaging/interfaces    T021 gallery_file_storage  T023 DTOs
T024 view permissions
```

### Parallel example: US1

```text
T036 test_photo_api.py     T037 test_gallery_legacy_reads.py     T038 test_gallery_access.py
```

---

## Implementation Strategy

### MVP (User Story 1)

Phases 1–3: the app uploads photos with thumbnails into existing albums; reads gain
`thumbnail_url`. Deployable on its own — together with T071's migration check and the thumbnail
command (T069–T070) if thumbnails for old photos are wanted on day one.

### Incremental delivery

1. MVP (US1) → deploy.
2. US2 + US3 → the app manages and shows the tree with covers → deploy.
3. US4 → covers → deploy.
4. US5 + US6 → ordering and metadata → deploy.
5. US7 + Polish → one-time backfill at deploy.

Every increment keeps old app versions working (T037).
