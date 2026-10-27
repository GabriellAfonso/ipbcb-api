# Quickstart: Bible Videos and Reading Progress

From `server/` with `.venv_windows` active.

## Automated

```powershell
python -m pytest features/bible core/tests/integration/test_management_access_matrix.py -q
python manage.py makemigrations --check --dry-run
```

Expected: all green; no pending migration.

## Manual (local server)

1. `python manage.py migrate` — applies `bible/0001`, the core scope migrations.
2. As a Liderança user, `POST /api/bible/videos/` with a real public link and
   `places: [{"book": "Gn", "chapter": 1}]` → 201 with the YouTube title. Same link again → 409
   `BIBLE_VIDEO_EXISTS` with `video`.
3. `GET /api/bible/videos/` without a token → 200 and an `ETag`; repeat with `If-None-Match` → 304.
4. A private or deleted video → 400 `BIBLE_VIDEO_UNAVAILABLE`.
5. As a Mídia user, the POST → 403.
6. As any member, `POST /api/bible/progress/sync/` with a chapter mark at 10:05 and an unmark of
   the same chapter at 10:00 → both accepted; `GET /api/bible/progress/` does list the chapter.

See [contracts/api.md](contracts/api.md) for bodies and errors.
