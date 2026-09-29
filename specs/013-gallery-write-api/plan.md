# Implementation Plan: Gallery Write API

**Branch**: `013-gallery-write-api` | **Date**: 2026-09-29 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/013-gallery-write-api/spec.md`

## Summary

Give the gallery a write API for the app's management panel. `Album` gains a nullable self
`parent` (PROTECT), `description`, `event_date`, `position` and its own `cover_image`; name
uniqueness moves to two conditional unique constraints (per parent, and among roots). `Photo`
gains `position`, `thumbnail` and `uploaded_by`. Tree order and inherited covers are computed
at read time by pure functions over the whole (small) album table, with cycle guards. Uploads
keep `core.files.image_validation`, add a 50 MP limit, store originals as
`gallery/{album_id}/{uuid}.{ext}`, and create a 1000 px JPEG thumbnail, and on an album's first
photo a 1000×1000 cover, through an `ImageProcessor` interface backed by Pillow. The Django admin
upload page and album form go through the same services. A data migration raises Liderança and
Mídia to `owner` on `gallery`; another backfills positions; a management command backfills
thumbnails.

## Technical Context

**Language/Version**: Python 3.14, `.venv_windows`

**Primary Dependencies**: Django 6.0, DRF 3.17, dependency-injector, Pydantic 2.12, Pillow 12.3
(already a dependency). No new dependency.

**Storage**: PostgreSQL in production, SQLite in tests; Django `default_storage` under
`MEDIA_ROOT` for files. Three migrations (data-model.md).

**Testing**: pytest + pytest-django; named fakes `FakeAlbumRepository`, `FakeGalleryRepository`,
`FakeGalleryFileStorage`, `FakeImageProcessor` in `features/gallery/tests/fakes.py`; real Pillow
only in the processor's integration test; migration tests with `MigrationExecutor` as in
`test_is_admin_conversion_migration.py`; mypy, ruff, bandit.

**Target Platform**: Linux container behind nginx, prefix `/ipbcb/`; media served per spec 009.

**Project Type**: Web service (REST API), single Android client.

**Performance Goals**: album list and cover resolution in 1 query + O(n) in memory; photo list
2 queries; upload of one ~5 MB phone JPEG, thumbnail included, well under the request timeout
(JPEG `draft` decode at reduced scale).

**Constraints**: services never see HTTP; ORM only in repositories; Pillow only in
`features/gallery/imaging/pillow_image_processor.py`; existing read fields unchanged; existing
files never moved; migrations 0001 (gallery) and 0005 (core) untouched.

**Scale/Scope**: hundreds of albums, low thousands of photos; 9 new endpoint-methods, 2 changed
reads; 3 roles.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design — result unchanged.*

| Rule (`specs/constitution.md`, `CLAUDE.md`) | Status |
|---|---|
| `IsAuthenticated` on every authenticated view; one scope per management endpoint | ✅ writes: `[IsAuthenticated, scope_permission(Scope.GALLERY)]`; mixed GET/POST routes split per method (R-07) |
| Levels from method, override only raises | ✅ no overrides; `DELETE` cover is `owner` by default |
| Views → services → repositories; ORM only in repositories | ✅ `AlbumRepository`, `GalleryRepository`; admin form and page call services (R-11) |
| Services never import HTTP objects | ✅ services take DTOs, `IO[bytes]`, user id |
| DI via `config/di.py`; injection, not globals | ✅ new providers; `features.gallery.admin` and new views wired |
| Third-party libs behind an owned interface | ✅ `ImageProcessor` Protocol (R-04); storage behind `GalleryFileStorage` (R-05) |
| DTOs are Pydantic | ✅ data-model.md DTOs; photo reads move from `QuerySet[Photo]` to `PhotoView` |
| Uploads validated by decoded content, size-checked first, streamed to storage | ✅ `detect_image_extension` first, unchanged; originals streamed; derivatives are bytes ≤ ~300 KB |
| Input validated by serializer; no raw `int()` on request fields | ✅ serializers for JSON bodies; `require_int` for multipart `album_id` |
| No queries in loops | ✅ whole-table album load; batched `bulk_update` for order; backfill command reads in batches (one write per photo is the backfill itself, R-13) |
| Error shape canonical | ✅ every error through domain exceptions + `extra_context()`; the all-rejected upload `400` is canonical plus `rejected` (clarification Q1) |
| Domain exceptions with offending value and expected shape | ✅ R-09 |
| Media: default deny by folder, no new rule | ✅ every new file under `gallery/` |
| Caching: user-dependent bodies private | ✅ n/a — gallery bodies do not depend on who asks (R-12) |
| Models have `__str__`, `Meta.ordering`, `Meta.verbose_name` | ✅ added to `Album` and `Photo` (they lack `Meta` today) |
| Migrations generated; data migrations with reason at top; no edit of applied ones | ✅ `gallery/0002` generated; `gallery/0003`, `core/0006` data with reason; verified on a production dump with a real rollback (quickstart §3) |
| Spec before code; spec and code in the same commit | ✅ step 0 updates `specs/gallery/spec.md`, `specs/gallery/plan.md`, spec 012 |
| Functions 4–20 lines, files < 500 lines | ✅ services split by responsibility (below) |

**Amendment to a prior feature (not a constitution violation)**: spec 012 FR-009 and SC-002 say
Liderança never holds `owner`. Raising it on `gallery` was decided by the requester; step 0
rewrites those statements (spec FR-020).

Gate: **pass**.

## Technical Decisions

Full reasoning in [research.md](research.md).

- **D-1** Sibling-unique names: two conditional `UniqueConstraint`s + service pre-check +
  `IntegrityError` translation (R-01).
- **D-2** Cycle check: pure `find_cycle` over a one-query parent map, under `select_for_update`
  of the album rows; every tree walk is cycle-safe (R-02).
- **D-3** `position` on both models, `max + 1` append under a row lock, full-list reorder with
  `bulk_update`, name / upload-time backfill (R-03).
- **D-4** `ImageProcessor` Protocol + `PillowImageProcessor`; constants in the services; order:
  validate → pixel limit → derivative (R-04).
- **D-5** `GalleryFileStorage`; files first, rows in a transaction, cleanup on failure, old
  cover deleted on commit; `photo_upload_path` kept for `0001` (R-05).
- **D-6** `tree_order` / `resolve_cover_sources` pure functions, photos sorted in Python (R-06).
- **D-7** Mixed-permission routes via `get_permissions()` helper (R-07).
- **D-8** Serializers → Pydantic DTOs, `model_fields_set` for absent vs null (R-08).
- **D-9** Eight new domain exceptions; Portuguese where the app user can trigger it (R-09).
- **D-10** `core/0006` swaps `gallery__manage` → `gallery__owner` for leader and media,
  reversible (R-10).
- **D-11** Admin: album form and save through `AlbumService`; photo add disabled; parent
  PROTECT (R-11).
- **D-12** `generate_photo_thumbnails` command over `GalleryService.fill_missing_thumbnails`
  (R-13).

## Service split

Keeps each file under 500 lines and one responsibility each; all registered in `config/di.py`.

| Service | Responsibility | Depends on |
|---------|----------------|------------|
| `AlbumService` | list (tree order + covers), create, update (rename/move/fields), reorder, `validate_placement` | `AlbumRepository`, `GalleryFileStorage` (cover URLs) |
| `AlbumCoverService` | replace, remove, `cover_from_first_photo` | `AlbumRepository`, `GalleryFileStorage`, `ImageProcessor` |
| `GalleryService` *(existing)* | photo reads, `upload_photos` (extended, validation kept), update, reorder, `fill_missing_thumbnails` | `GalleryRepository`, `AlbumRepository`, `GalleryFileStorage`, `ImageProcessor`, `AlbumCoverService` |

## Implementation Order

Each step leaves the tree type-correct for the whole-tree mypy hook.

0. **Specs** (with the code commits of step 2 onward, per CLAUDE.md §6.2): rewrite
   `specs/gallery/spec.md` and `specs/gallery/plan.md` to the target state; amend spec 012 (matrix,
   `gallery` note, FR-009, SC-002, User Story 2, "Leader + Media" edge case).
1. **Domain**: exceptions in `core/domain/exceptions.py`; `features/gallery/domain/album_tree.py`
   (`AlbumNode`, `find_cycle`, `tree_order`, `resolve_cover_sources`) and
   `domain/gallery_rules.py` (name trim, name cut keeping extension, order-set comparison). Unit
   tests, including the cycle regressions.
2. **Models + migrations**: fields, `Meta`, constraints, indexes; `makemigrations gallery` →
   `0002`; hand-write `0003_backfill_positions.py` (reason at top). Constraint regression test
   (two roots with one name), migration test.
3. **Role raise**: `core/0006_gallery_owner_for_leader_media.py`; migration test forward and
   back; update `test_panel_roles_seed.py` and the gallery row of the access matrix test.
4. **Imaging + storage**: `ImageProcessor` Protocol, `PillowImageProcessor`, integration test on
   generated images; `GalleryFileStorage` + default-storage implementation; fakes.
5. **Repositories + DTOs**: `AlbumRepository` (new), `GalleryRepository` extended; DTOs;
   repository integration tests.
6. **Services**: `AlbumService`, `AlbumCoverService`, extended `GalleryService`; DI providers;
   unit tests with fakes.
7. **Album endpoints**: serializers, views, URLs (`api/albums/`, `api/albums/<id>/`,
   `api/albums/order/`, `api/albums/<id>/cover/`); permission helper; API + access tests.
8. **Photo endpoints**: `POST api/photos/`, `PATCH api/photos/<id>/`,
   `PUT api/albums/<id>/photos/order/`; photo reads switch to `PhotoView` with `thumbnail_url`
   and the `404`; legacy-reads test.
9. **Admin**: album form/save via service, parent field, photo add disabled, upload page through
   the extended service; admin tests (existing `test_upload.py`, `test_build_upload_html.py`,
   `core/tests/test_admin_registrations.py` adjusted).
10. **Backfill command** + test; `media_rules.py` comment (R-14).
11. **Validation**: quickstart §1–§4, §3 against the production dump.

## Project Structure

### Documentation (this feature)

```text
specs/013-gallery-write-api/
├── spec.md
├── plan.md                    # this file
├── research.md                # R-01 … R-14
├── data-model.md
├── quickstart.md
├── contracts/gallery-api.md
├── checklists/requirements.md
└── tasks.md                   # /speckit-tasks
```

### Source Code

```text
server/
├── config/di.py                                   # new providers; wire admin + new views
├── core/
│   ├── domain/exceptions.py                       # 8 gallery exceptions (R-09)
│   ├── migrations/0006_gallery_owner_for_leader_media.py
│   └── tests/integration/test_gallery_owner_migration.py, test_panel_roles_seed.py,
│       test_management_access_matrix.py
└── features/
    ├── media/domain/media_rules.py                # comment only (R-14)
    └── gallery/
        ├── admin.py                               # AlbumAdmin form/save via service; PhotoAdmin
        ├── domain/
        │   ├── album_tree.py                      # AlbumNode, find_cycle, tree_order, resolve_cover_sources
        │   └── gallery_rules.py                   # names, order-set comparison
        ├── dtos/gallery_dtos.py                   # data-model.md DTOs
        ├── imaging/
        │   ├── interfaces.py                      # ImageProcessor Protocol
        │   └── pillow_image_processor.py
        ├── management/commands/generate_photo_thumbnails.py
        ├── migrations/0002_….py, 0003_backfill_positions.py
        ├── models/gallery.py
        ├── repositories/
        │   ├── interfaces.py                      # AlbumRepository, GalleryRepository, GalleryFileStorage
        │   ├── album_repository.py
        │   ├── gallery_repository.py
        │   └── gallery_file_storage.py
        ├── serializers/
        │   ├── serializers.py                     # PhotoSerializer (reads + upload)
        │   └── album_serializers.py
        ├── services/
        │   ├── album_service.py
        │   ├── album_cover_service.py
        │   └── gallery_service.py
        ├── urls.py
        ├── views/
        │   ├── permissions.py                     # member_read_gallery_write_permissions
        │   ├── albums.py                          # list/create, detail, order
        │   ├── album_cover.py
        │   ├── gallery.py                         # photo list/upload, album photos, photo detail, photo order
        │   └── upload.py                          # admin page (kept)
        └── tests/
            ├── fakes.py
            ├── unit/…
            └── integration/…                      # per quickstart §1
```

**Structure Decision**: everything stays in `features/gallery`, split by layer like the other
features; `imaging/` is new, holding the only Pillow derivative code. Nothing moves to `core`
except the domain exceptions (their home by convention) and the role migration (roles live in
`core`).

## Out of scope, found during planning (reported, not changed)

- Existing gallery files keep camera-style names; the `media_rules` content-type table remains
  their protection.
- The ETag/`304` helper is not added to gallery reads; the app downloads the album list each
  time. Revisit if list size grows.

## Complexity Tracking

No constitution violations to justify.
