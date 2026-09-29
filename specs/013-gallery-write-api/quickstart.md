# Quickstart: validating the gallery write API

Commands run from `server/` with `.venv_windows` active (PowerShell). Contract details in
[contracts/gallery-api.md](contracts/gallery-api.md); fields in [data-model.md](data-model.md).

## 1. Automated checks

```powershell
pytest
mypy .
ruff check .
```

Expected: all green. The tests that carry this feature:

| What | Where (planned) | Proves |
|------|-----------------|--------|
| Cycle detection, tree order, cover resolution (depth-first, cycle-safe) | `features/gallery/tests/unit/test_album_tree.py` | FR-006, FR-008, FR-010, FR-015 |
| Name trim/cut, order-set comparison | `features/gallery/tests/unit/test_gallery_rules.py` | FR-011, Edge Cases |
| Album service with fakes (create, move, rename, order, duplicate, cycle) | `features/gallery/tests/unit/test_album_service.py` | FR-004–FR-007, FR-009, FR-011 |
| Upload with `FakeImageProcessor` / `FakeGalleryFileStorage` (partial success, thumbnail failure, pixel limit, EXIF date, auto cover, file cleanup on DB failure) | `features/gallery/tests/unit/test_gallery_service.py` | FR-013, FR-016–FR-018 |
| Cover replace/remove | `features/gallery/tests/unit/test_album_cover_service.py` | FR-012, FR-014 |
| Pillow processor on real bytes (square, bounded, GIF frame, alpha, EXIF orientation/date, corrupt input) | `features/gallery/tests/integration/test_pillow_image_processor.py` | Definitions, Edge Cases |
| **Regression**: two roots with one name refused by the database | `features/gallery/tests/integration/test_album_constraints.py` | FR-005, US2-3 |
| **Regression**: move under self / under descendant → 400, tree unchanged | `features/gallery/tests/integration/test_album_api.py` | FR-006, US2-5/6 |
| Every endpoint × {Admin, Liderança, Mídia, member without role, non-member} | `features/gallery/tests/integration/test_gallery_access.py` | FR-001–FR-003, SC-007 |
| Photo API: upload 201/207/400 bodies, PATCH, order, 404s | `features/gallery/tests/integration/test_photo_api.py` | FR-016–FR-019c |
| Admin upload goes through the service; admin blocks cycle and duplicate | `features/gallery/tests/integration/test_gallery_admin.py` | FR-005, FR-019a |
| Backfill command idempotent, skips unreadable | `features/gallery/tests/integration/test_generate_photo_thumbnails.py` | FR-019b |
| Position backfill + role raise migrations, forward and back | `features/gallery/tests/integration/test_position_backfill_migration.py`, `core/tests/integration/test_gallery_owner_migration.py` | FR-003, FR-009 |
| Seeded roles and access matrix now say `owner` on `gallery` | `core/tests/integration/test_panel_roles_seed.py`, `test_management_access_matrix.py` | FR-003 |

## 2. Old app compatibility

```powershell
pytest features/gallery/tests/integration/test_gallery_legacy_reads.py
```

Expected: `GET /api/photos/` and `GET /api/albums/{id}/photos/` keep every field they returned
before (`id`, `name`, `description`, `album_id`, `album_name`, `image_url`, `date_taken`,
`uploaded_at`); only `thumbnail_url` is added; an unknown album is `404`.

## 3. Migrations against a restored production dump

1. Restore the latest production dump into a local PostgreSQL.
2. Before migrating, record:
   - `SELECT id, name FROM gallery_album ORDER BY name;`
   - `SELECT album_id, id, uploaded_at FROM gallery_photo ORDER BY album_id, uploaded_at, id;`
   - `SELECT g.name, p.codename FROM auth_group g JOIN auth_group_permissions gp ON gp.group_id = g.id JOIN auth_permission p ON p.id = gp.permission_id WHERE p.codename LIKE 'gallery__%';`
3. `python manage.py migrate`.
4. Check:
   - every album has `parent_id IS NULL`, positions `0..n-1` in the name order of step 2;
   - each album's photos have positions `0..n-1` in the order of step 2;
   - `leader` and `media` hold `gallery__owner` and not `gallery__manage`;
   - `image` of every existing photo is unchanged (no file moved).
5. Roll back and prove it: `python manage.py migrate gallery 0001` and
   `python manage.py migrate core 0005` → the groups hold `gallery__manage` again, the new
   columns are gone. Migrate forward again → same state as step 4.
6. `python manage.py generate_photo_thumbnails` → prints `filled N, skipped 0`; run again →
   `filled 0`. Every photo now has a file under `gallery/thumbs/{album_id}/`.

## 4. Manual walk-through (dev server, `DEBUG=True`)

1. Log in as a Mídia user. `POST /api/albums/` `{"name": "Retiros"}` → `201`; again with the same
   name → `400`.
2. Create "2026" under "Retiros"; `PATCH` "Retiros" with `parent_id` of "2026" → `400` naming both.
3. `POST /api/photos/` into "2026" with one JPEG → `201`; `GET /api/albums/` → "2026" has its own
   cover, "Retiros" shows the same `cover_url` with `cover_source_album_id` of "2026".
4. Open `thumbnail_url` and `cover_url` with the member's token → `200`, a JPEG of the expected
   size; without a token → `401` (spec 009 unchanged).
5. `DELETE /api/albums/{2026}/cover/` → `204`; list → both albums have `cover_url: null`.
6. As a member without a role: any write → `403`; reads → `200`.
