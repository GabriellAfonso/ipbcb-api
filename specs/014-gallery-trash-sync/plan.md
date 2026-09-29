# Implementation Plan: Gallery Trash and Change Feed

**Branch**: `014-gallery-trash-sync` | **Date**: 2026-09-29 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/014-gallery-trash-sync/spec.md`

## Summary

Soft delete for albums and photos, grouped in deletion batches, with a 30-day trash, exact batch
restore and a daily purge of rows and files; plus a pull change feed for the Android app.

`Album` and `Photo` gain `deleted_at`, `deletion_batch` (FK to a new `GalleryDeletionBatch`) and
`updated_at`. Their default manager becomes live-only, so every 013 read, the admin and the
upload page hide trashed rows without being touched. The sibling-name constraints become
live-only. A delete locks the album table (as 013's moves do), trashes the subtree in one batch
and writes one `GalleryDeletionMark` per row. Marks outlive the purge for 90 days and feed
`deleted_*_ids`. The media check of spec 009 asks the gallery, through a port wired in
`config/di.py`, whether a `gallery/` file belongs to a trashed row: one `UNION` query over three
partial indexes, skipped for owners who are members. The feed uses an opaque timestamp cursor
with a 90 s overlap, so a late commit is never missed. Derived changes (a resolved cover, a
photo's `album_name`, positions) bump `updated_at` exactly, by comparing the album tree before
and after each write. Both resources gain `position`. The admin can no longer delete.
`Photo.album` becomes `PROTECT`, so only the purge removes rows, and always with their files.

## Technical Context

**Language/Version**: Python 3.14, `.venv_windows`

**Primary Dependencies**: Django 6.0, DRF 3.17, dependency-injector, Pydantic 2.12. No new
dependency.

**Storage**: PostgreSQL in production, SQLite in tests; `default_storage` under `MEDIA_ROOT`. One
generated migration, `gallery/0004` (R-15). No data migration.

**Testing**: pytest + pytest-django; named fakes in `features/gallery/tests/fakes.py`
(`FakeTrashRepository`, `FakeDeletionMarkRepository`, `FakeClock`, plus the 013 fakes extended),
`FakeTrashedMediaLookup` in `features/media/tests/`; mypy, ruff, bandit.

**Target Platform**: Linux container behind nginx, prefix `/ipbcb/`; media per spec 009;
purge scheduled by host cron (R-10).

**Project Type**: Web service (REST API), single Android client.

**Performance Goals**: media check on `gallery/` adds at most one indexed probe of a tiny partial
index (none for owner members); feed delta: 1 album query, 1 photo query, 2 mark queries; trash
listing: 4 queries whatever its size; delete/restore: bulk `UPDATE`s, no per-row queries.

**Constraints**: features never import each other (media ↔ gallery through a Protocol + DI);
services never see HTTP; ORM only in repositories; existing responses only gain `position`;
migrations 0001–0003 untouched; `core/domain/exceptions.py` stays under 500 lines (389 now, ~+60).

**Scale/Scope**: hundreds of albums, low thousands of photos, tens of trash entries; 6 new
endpoint-methods, 1 changed media rule, 1 management command.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design; result unchanged.*

| Rule (`specs/constitution.md`, `CLAUDE.md`) | Status |
|---|---|
| `IsAuthenticated` on every authenticated view; one scope per management endpoint | ✅ trash/restore: `[IsAuthenticated, scope_permission(Scope.GALLERY, overrides)]`; `DELETE` via `GALLERY_WRITE`; feed `IsMemberUser` |
| Overrides only raise the level | ✅ `GET`/`POST` → `owner` on trash and restore, checked by `validate_overrides` at import |
| Features never import each other | ✅ `TrashedMediaLookup` Protocol in `features/media`; gallery implements it structurally; wired in `config/di.py` (R-05) |
| Views → services → repositories; ORM only in repositories | ✅ `TrashRepository`, `DeletionMarkRepository`, `GalleryTrashedFileLookup`; the managers are model code |
| Services never import HTTP objects | ✅ services take ids, actor UUID, the raw `since` string |
| DI via `config/di.py`; injection, not globals | ✅ new providers; `Clock` injected into repositories and services |
| DTOs are Pydantic | ✅ `TrashEntry`, `TrashOutcome`, `PurgeReport`, `ChangeFeed` (data-model.md) |
| Input validated; no raw `int()` on request fields | ✅ ids from URL converters; `since` never parsed by the view; bad cursor is not an error by design (spec Edge Cases) |
| No queries in loops | ✅ bulk `UPDATE`s by id list; marks via one `bulk_create(update_conflicts=True)`; trash counts by subquery; purge loops per batch by design (one transaction each, R-09) |
| Error shape canonical; domain exceptions with offending values | ✅ 4 new exceptions with `extra_context` (data-model.md) |
| Media: default deny by folder; validated path is the served path | ✅ unchanged; the trash check runs on the validated path, after the folder rule and permission |
| Media caching exception | ✅ unchanged; `no-cache` means the next revalidation of a trashed file gets `404` |
| Caching of user-dependent bodies | ✅ n/a: trash and feed bodies do not depend on who asks within the allowed audience (as 013 R-12) |
| Structured JSON logs, ids only | ✅ R-14 |
| Models have `__str__`, `Meta.ordering`, `Meta.verbose_name` | ✅ both new models |
| Migrations generated; data migrations with reason; applied ones untouched | ✅ `0004` generated; no data migration; verified on a production dump with a real rollback (quickstart §3) |
| Spec before code; spec and code in the same commit | ✅ step 0 |
| Functions 4–20 lines, files < 500 lines | ✅ service split below |

**Amendments to prior specs (not violations)**: spec 009 FR-009 ("access MUST NOT depend on any
database record") and its orphan-files edge case change for `gallery/`; spec 012 gains the new
endpoints; both are listed in spec FR-041/FR-042 and done in step 0.

Gate: **pass**.

## Technical Decisions

Full reasoning in [research.md](research.md).

- **D-1** Trash state: `deleted_at` + `deletion_batch` on rows, `GalleryDeletionBatch` table with
  root, time and actor (R-01).
- **D-2** Live-only default managers, `all_objects` for trash code; live-only partial unique
  constraints; lock queries that find no row raise `404` (R-02).
- **D-3** Delete: album-table lock, pure `subtree_ids`, bulk `UPDATE`s, marks, exact cover
  bumps (R-03).
- **D-4** Restore: root-only, parent-live and name checks, batch cleared, marks removed (R-04).
- **D-5** Media: `TrashedMediaLookup` port, one `UNION` query on three partial indexes,
  `can_own_gallery` on the viewer, new `trashed` outcome (R-05).
- **D-6** `updated_at` set explicitly through an injected `Clock`; derived changes bumped
  exactly by `changed_cover_albums(before, after)` (R-06).
- **D-7** Cursor `v1.<base64url µs>`, 90 s overlap (clarified), full sync on
  old/malformed/future/unknown (R-07).
- **D-8** `GalleryDeletionMark` upserted per row, removed on restore, expired by the daily
  command after 90 days (R-08).
- **D-9** Purge per batch, one transaction each, descendants first, files on commit;
  `Photo.album` → `PROTECT` (R-09).
- **D-10** Host cron, daily (R-10).
- **D-11** Endpoint permissions (R-11).
- **D-12** Admin delete disabled (clarified) (R-12).
- **D-13** Trash listing in 4 queries (R-13).
- **D-14** Log events (R-14).
- **D-15** One generated migration, no data migration (R-15).
- **D-16** `position` on both resources (R-16).

## Spec adjustments made while planning

Recorded in the spec's Clarifications, same commit:

- SC-006 and US3-2: with the overlap (D-7), "a sync with no changes transfers nothing" holds for
  a sync made more than 90 s after the last change; items changed within 90 s before a cursor
  may be returned again.
- FR-033: "the purge MUST NOT remove deletion marks" means that removing a row never removes its
  mark. The same daily command drops marks past `MARK_RETENTION`, in a separate step.
- FR-012: the admin option taken is "not offered" (D-12).
- Gallery domain spec: `Photo.album` becomes `PROTECT` (D-9).

## Service split

| Service | Responsibility | Depends on |
|---------|----------------|------------|
| `GalleryTrashService` (new) | `delete_album`, `delete_photo`, `list_trash`, `restore_album`, `restore_photo` | `AlbumRepository`, `GalleryRepository`, `TrashRepository`, `DeletionMarkRepository`, `CoverChangeTracker`, `GalleryFileStorage`, `Clock` |
| `GalleryPurgeService` (new) | `purge_expired` | `TrashRepository`, `DeletionMarkRepository`, `GalleryFileStorage`, `Clock` |
| `GalleryChangeFeedService` (new) | `changes(since)` | `AlbumService` (views), `GalleryRepository`, `DeletionMarkRepository`, `Clock` |
| `CoverChangeTracker` (new, small) | `snapshot()` / `touch_changed(before)`: bump albums whose resolved cover changed | `AlbumRepository` |
| `AlbumService` *(013)* | + bump photos on rename; cover tracking on move, create, reorder; `position` in views | + `CoverChangeTracker` |
| `AlbumCoverService` *(013)* | + cover tracking on replace, remove, automatic | + `CoverChangeTracker` |
| `GalleryService` *(013)* | reads unchanged (live via manager); `position` in views | unchanged |
| `MediaAccessService` *(009)* | + trash check for `gallery/` | + `TrashedMediaLookup` |

## Implementation Order

Each step leaves the tree type-correct for the whole-tree mypy hook (memory: commit splitting).

0. **Specs** (in the commit with the first code step, CLAUDE.md §6.2): rewrite
   `specs/gallery/spec.md`, `plan.md` and `tasks.md` to the target state (trash, restore, purge,
   feed, media rule, `position`, `PROTECT`, admin without delete, 013's "belongs to feature
   014" removed); amend spec 009 (FR-005 `gallery` row, FR-009, orphan-files edge case, "No
   database lookup" assumption) and spec 012 (Endpoint Classification gains a `gallery`
   section); apply the spec adjustments above.
1. **Domain**: `domain/trash_rules.py` (constants, `subtree_ids`, `purge_order`, `purge_on`),
   `domain/feed_cursor.py` (encode, decode, `feed_window`, full-sync decision),
   `changed_cover_albums` in `domain/album_tree.py`; the 4 exceptions. Unit tests.
2. **Models + migration**: managers, fields, the two models, constraints, partial indexes,
   `PROTECT`; `makemigrations gallery` → `0004`. Constraint regression (name reuse after trash),
   migration forward/back test.
3. **Clock into repositories**: `AlbumRepositoryImpl` and `GalleryRepositoryImpl` take `clock`;
   every write sets `updated_at`; `apply_order` writes changed rows only; lock queries raise
   when the row is gone; `touch`, `touch_photos_of`, `live_sibling_named`,
   `list_photos_changed_since`. DI reordered (clock before gallery). Repository tests, including
   the upload-vs-delete race.
4. **`position` in resources**: DTOs, `_to_view`, serializers; legacy-reads test updated.
5. **`CoverChangeTracker`** and its use in `AlbumService` and `AlbumCoverService`; rename bumps
   photos. Unit tests.
6. **Trash**: `TrashRepositoryImpl`, `DeletionMarkRepositoryImpl`, DTOs, `GalleryTrashService`,
   DI; `DELETE` on album and photo detail views; `views/trash.py`, serializers, URLs. Unit,
   API, access and invisibility tests.
7. **Media**: `TrashedMediaLookup` Protocol, `GalleryTrashedFileLookup`, `MediaViewer.
   can_own_gallery`, service flow, `trashed` outcome, DI. Unit and integration tests
   (member / owner / cascaded / cover / legacy path / non-gallery unaffected).
8. **Feed**: `GalleryChangeFeedService`, `views/changes.py`, serializer, URL, DI. Unit tests
   with a fake clock, API test across a purge.
9. **Purge**: `GalleryPurgeService`, `purge_gallery_trash` command, DI wiring. Unit and
   integration tests (`PROTECT` order, skip and continue, files after commit, idempotent, mark
   expiry).
10. **Admin**: `has_delete_permission` → `False` on both; admin tests.
11. **Access matrix**: new endpoints in `core/tests/integration/test_management_access_matrix.py`.
12. **Validation**: quickstart §1–§5, §3 against the production dump.

## Project Structure

### Documentation (this feature)

```text
specs/014-gallery-trash-sync/
├── spec.md
├── plan.md                        # this file
├── research.md                    # R-01 … R-16
├── data-model.md
├── quickstart.md
├── contracts/gallery-trash-api.md
├── checklists/requirements.md
└── tasks.md                       # /speckit-tasks
```

### Source Code

```text
server/
├── config/di.py                                   # clock first; new repos/services; media lookup; wiring
├── core/
│   ├── domain/exceptions.py                       # 4 exceptions
│   └── tests/integration/test_management_access_matrix.py
└── features/
    ├── media/
    │   ├── domain/media_rules.py                  # MediaAccessOutcome.TRASHED
    │   ├── dtos/media_dtos.py                     # MediaViewer.can_own_gallery
    │   ├── repositories/interfaces.py             # TrashedMediaLookup Protocol
    │   ├── services/media_access_service.py       # trash check for gallery/
    │   ├── views/media_file.py                    # computes can_own_gallery
    │   └── tests/…                                # FakeTrashedMediaLookup, new cases
    └── gallery/
        ├── admin.py                               # delete disabled
        ├── domain/
        │   ├── album_tree.py                      # + changed_cover_albums
        │   ├── feed_cursor.py                     # new
        │   └── trash_rules.py                     # new
        ├── dtos/
        │   ├── gallery_dtos.py                    # + position, updated_at
        │   ├── trash_dtos.py                      # new
        │   └── feed_dtos.py                       # new
        ├── management/commands/purge_gallery_trash.py
        ├── migrations/0004_….py                   # generated
        ├── models/
        │   ├── gallery.py                         # managers, fields, PROTECT, constraints, indexes
        │   └── trash.py                           # GalleryDeletionBatch, GalleryDeletionMark
        ├── repositories/
        │   ├── interfaces.py                      # + TrashRepository, DeletionMarkRepository
        │   ├── album_repository.py                # clock, touch, live_sibling_named
        │   ├── gallery_repository.py              # clock, list_photos_changed_since
        │   ├── trash_repository.py                # new
        │   ├── deletion_mark_repository.py        # new
        │   └── trashed_file_lookup.py             # new, implements media's port
        ├── serializers/
        │   ├── serializers.py, album_serializers.py   # + position
        │   ├── trash_serializers.py               # new
        │   └── feed_serializers.py                # new
        ├── services/
        │   ├── cover_change_tracker.py            # new
        │   ├── gallery_trash_service.py           # new
        │   ├── gallery_purge_service.py           # new
        │   ├── gallery_change_feed_service.py     # new
        │   └── album_service.py, album_cover_service.py   # tracker, rename bump
        ├── urls.py                                # 4 routes
        ├── views/
        │   ├── albums.py, gallery.py              # + delete
        │   ├── trash.py                           # new
        │   └── changes.py                         # new
        └── tests/                                 # per quickstart §1
```

**Structure Decision**: everything stays in `features/gallery`, split by layer like 013. The new
models go to their own `models/trash.py`, so `gallery.py` stays about albums and photos. The only
touch on `features/media` is the port and the rule. The purge schedule lives outside the
repository.

## Dependencies (outside this repository)

- **Host cron** on the production server: daily `purge_gallery_trash` (R-10, quickstart §6).
  Recorded here and in the gallery domain spec; like the nginx config, this is its only record.
- **Android app** (separate spec): consumes the feed and removes deleted photos from the device.
  Not required for the backend to ship: deleted files are `404` to old apps already.

## Out of scope, found during planning (reported, not changed)

- A command that lists orphan `gallery/` files (clarified: later, outside 014).
- The feed has no pagination; a full sync is as large as `GET /api/photos/` today.

## Complexity Tracking

No constitution violations to justify.
