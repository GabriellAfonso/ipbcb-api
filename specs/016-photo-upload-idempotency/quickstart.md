# Quickstart: Idempotent Photo Upload

Validation guide. Contract: [contracts/photo-upload-api.md](contracts/photo-upload-api.md);
model and rules: [data-model.md](data-model.md).

Commands run from `server/` in PowerShell with `.venv_windows` active.

## 1. Automated tests

```powershell
python -m pytest features/gallery core -q
```

Expected: all pass, and the 013 upload tests pass **unchanged** (SC-003). New coverage:

| Area | File | Proves |
|------|------|--------|
| id rules | `features/gallery/tests/unit/test_upload_rules.py` | length, characters, file count, messages carry value and shape (US4) |
| single value | `core/tests/unit/test_parsing_guards.py` | repeated field is `400` naming it |
| service | `features/gallery/tests/unit/test_upload_dedup.py` (new) | first upload stores the id; live repeat stores nothing and skips album and file checks; trashed → `409`; lost race cleans files and answers the winner; log lines (US1, US2, US5) |
| repository | `features/gallery/tests/integration/test_gallery_repository.py` | id written; duplicate insert → `ClientUploadIdTakenError`; lookup sees trashed rows |
| API | `features/gallery/tests/integration/test_upload_idempotency_api.py` (new) | `201` twice with one photo; moved photo returned; trashed `409`; the `400`s; id absent from the resource; no id → 013 behaviour |
| migration | `features/gallery/tests/integration/test_client_upload_id_migration.py` (new) | forward and back on existing rows |
| admin | `features/gallery/tests/unit/test_upload.py`, `features/gallery/tests/integration/test_gallery_admin.py` | upload page stores no id; photo page neither shows nor edits it |

## 2. Manual, dev server

```powershell
$token = "<access token of a Mídia user>"
$id = [guid]::NewGuid().ToString()
curl.exe -s -H "Authorization: Bearer $token" -F album_id=7 -F "client_upload_id=$id" -F image=@IMG_0042.jpg http://localhost:8000/ipbcb/api/photos/
curl.exe -s -H "Authorization: Bearer $token" -F album_id=7 -F "client_upload_id=$id" -F image=@IMG_0042.jpg http://localhost:8000/ipbcb/api/photos/
```

Expected: both `201` with the same `accepted[0].id`; `GET /api/albums/7/photos/` lists it once;
the log has one `gallery_upload_deduplicated`. Delete the photo, send again: `409` `CONFLICT`.

## 3. Real race, PostgreSQL dev stack

Fire the same request twice in parallel with one fresh id:

```powershell
$id = [guid]::NewGuid().ToString()
1..2 | ForEach-Object -Parallel { curl.exe -s -o NUL -w "%{http_code}`n" -H "Authorization: Bearer $using:token" -F album_id=7 -F "client_upload_id=$using:id" -F image=@IMG_0042.jpg http://localhost:8000/ipbcb/api/photos/ }
```

(`ForEach-Object -Parallel` needs PowerShell 7; with 5.1 use two `Start-Job`.) Expected: two
`201`; one row with that id; no file under `media/gallery/7/` or `media/gallery/thumbs/7/`
without a row (SC-001, SC-002).

## 4. Migration on a production dump

```powershell
python manage.py migrate gallery 0006
python manage.py migrate gallery 0005
python manage.py migrate gallery 0006
```

Against a restored production dump. Expected: each step succeeds; the photo count is unchanged;
every existing photo has `client_upload_id` `NULL`.
