# Quickstart: validating the gallery trash and change feed

Commands run from `server/` with `.venv_windows` active (PowerShell). Contract details in
[contracts/gallery-trash-api.md](contracts/gallery-trash-api.md); fields in
[data-model.md](data-model.md); decisions in [research.md](research.md).

## 1. Automated checks

```powershell
pytest
mypy .
ruff check .
```

Expected: all green. The tests that carry this feature (planned locations):

| What | Where | Proves |
|------|-------|--------|
| `subtree_ids`, `purge_order`, `purge_on` (cycle-safe) | `features/gallery/tests/unit/test_trash_rules.py` | FR-003, FR-032 |
| `changed_cover_albums` (own cover replaced, descendant trashed, restored, reordered) | `features/gallery/tests/unit/test_album_tree.py` | FR-008, FR-034 |
| Cursor encode/decode, overlap window, full-sync thresholds, malformed/future/unknown version | `features/gallery/tests/unit/test_feed_cursor.py` | FR-036, FR-038 |
| Trash service with fakes: cascade, batch exactness, 404 on re-delete, restore refusals, marks written/removed | `features/gallery/tests/unit/test_gallery_trash_service.py` | FR-001–FR-005, FR-016–FR-023 |
| Purge service with fakes: order, one failing batch skipped, files only after commit, marks untouched, expiry | `features/gallery/tests/unit/test_gallery_purge_service.py` | FR-031–FR-033 |
| Feed service with a fake clock: full sync, delta, deleted ids, restore, derived changes | `features/gallery/tests/unit/test_gallery_change_feed_service.py` | FR-034–FR-039a |
| Media service: the four rows of the decision table, and no lookup outside `gallery/` | `features/media/tests/unit/test_media_access_service.py` | FR-024–FR-030 |
| **Regression**: cascade and exact batch restore (P1 trashed before A stays trashed) | `features/gallery/tests/integration/test_trash_api.py` | US2-7, US4-3 |
| **Regression**: name reuse after delete; restore refused on conflict, succeeds after rename | `features/gallery/tests/integration/test_trash_api.py`, `test_album_constraints.py` | FR-010, FR-021 |
| **Regression**: invisibility in every read (album list, photo list, album photos `404`, resolved cover, automatic cover, order sets) | `features/gallery/tests/integration/test_trash_invisibility.py` | FR-006–FR-011 |
| **Regression**: media rule, member `404` / owner `200` on a trashed photo, a cascaded photo, a trashed cover, and a pre-013 path | `features/gallery/tests/integration/test_media_trashed_gallery_files.py` | FR-024–FR-027 |
| **Regression**: purge of A → B → C with `PROTECT` | `features/gallery/tests/integration/test_purge_gallery_trash.py` | FR-032, US5-3 |
| **Regression**: change feed across a purge (id still deleted after the row is gone) | `features/gallery/tests/integration/test_change_feed_api.py` | FR-035, US3-5 |
| Upload racing a delete: the lock query finding no row raises `404` | `features/gallery/tests/integration/test_gallery_repository.py` | Edge Cases, R-02 |
| Every new endpoint × {Admin, Liderança, Mídia, member without role, non-member} | `features/gallery/tests/integration/test_gallery_access.py` | FR-001, FR-013, FR-016, FR-036 |
| Admin offers no delete; trashed albums absent from changelist, parent choice, upload page | `features/gallery/tests/integration/test_gallery_admin.py` | FR-012 |
| Access matrix and 012 classification include the new endpoints | `core/tests/integration/test_management_access_matrix.py` | FR-042 |

## 2. Old app compatibility

```powershell
pytest features/gallery/tests/integration/test_gallery_legacy_reads.py
```

Expected: every field returned before 014 is still there with the same meaning; `position` is
added last; trashed items are absent.

## 3. Migration against a restored production dump

1. Restore the latest production dump into a local PostgreSQL.
2. Record `SELECT count(*) FROM gallery_album;` and `SELECT count(*) FROM gallery_photo;`.
3. `python manage.py migrate` → `gallery 0004` applies.
4. Check: counts unchanged; every row has `deleted_at IS NULL` and a non-null `updated_at`;
   `\d gallery_album` shows `unique_live_album_name_per_parent`,
   `unique_live_root_album_name` and the partial index on `cover_image`; `\d gallery_photo` shows
   the two partial indexes. (`PROTECT` on `Photo.album` is enforced by Django, not by the
   database, so it is proved by the purge test, not here.)
5. Roll back and prove it: `python manage.py migrate gallery 0003` → the 013 constraints are
   back, the new columns and tables are gone, counts unchanged. Migrate forward again → same
   state as step 4.
6. `EXPLAIN` the media lookup (R-05) for one trashed photo path → both branches use the partial
   indexes (`Index Scan using photo_trashed_image` / `…_thumbnail` / `album_trashed_cover`).

## 4. Manual walk-through (dev server, `DEBUG=True`)

1. As Mídia: create album A with sub-album B, upload one photo into each. Note their file URLs.
2. As a member: `GET /api/gallery/changes/` → everything, `full_sync_required: false`; keep the
   `cursor`.
3. As Mídia: `DELETE /api/albums/{A}/` → `204`.
4. As a member: `GET /api/albums/` and `GET /api/photos/` → neither A, B nor their photos.
   Open the noted file URLs → `404`. `GET /api/gallery/changes/?since=<cursor>` →
   `deleted_album_ids: [A, B]`, `deleted_photo_ids` both photos.
5. As Mídia: open the same file URLs → `200`. `GET /api/gallery/trash/` → one entry, album A,
   `sub_album_count: 1`, `photo_count: 2`, `purge_on` 30 days ahead.
6. Create a new album named like A in the same place → `201`. Restore A → `400` naming the new
   album. Rename the new one, restore A → `200`; the member's feed now returns A, B and the
   photos as changed and no longer as deleted.
7. As a member without a role: `DELETE`, trash and restore → `403`; feed → `200`.
8. Django admin: album and photo pages show no "Delete" button and no bulk delete action.

## 5. Purge

1. Trash a small album tree, then move its batch back in time in a shell:
   `GalleryDeletionBatch.objects.update(deleted_at=F("deleted_at") - timedelta(days=31))` and the
   same on its rows (tests use a fake clock instead).
2. `python manage.py purge_gallery_trash` → `purged 1 batches (…); skipped 0; …`. Rows and files
   are gone; the member feed with an old cursor still lists the ids as deleted.
3. Run it again → `purged 0 batches`.

## 6. Deploy

Order, all on the same day:

1. **Backend** (this feature). Migrations run at container start (`compose.prod.yml`).
2. **Host cron**, on the production server, outside this repository:
   `30 3 * * * docker exec ipbcb-server-prod python manage.py purge_gallery_trash`. Until it
   exists nothing is purged, and nothing breaks: the trash just keeps growing.
3. **Android app**: consumes the feed, removes deleted photos locally. Old app versions keep
   working without it: deleted files are already `404` for them.
