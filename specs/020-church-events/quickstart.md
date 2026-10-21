# Quickstart: validating Church Events

Run from `server/` with the Windows venv (`..\.venv_windows\Scripts\python.exe`).

## Automated

```powershell
..\.venv_windows\Scripts\python.exe -m pytest features/events features/media features/gallery core -q
..\.venv_windows\Scripts\python.exe -m mypy .
..\.venv_windows\Scripts\python.exe manage.py makemigrations --check --dry-run
..\.venv_windows\Scripts\python.exe manage.py spectacular --validate --fail-on-warn --file NUL
```

Full suite once at the end: `python -m pytest -q`.

## Manual (development server, `DEBUG=True`)

1. `python manage.py migrate` — applies `events.0001_initial` and
   `core.0008_events_owner_for_leader_media`. In the Django admin, check that groups `leader` and
   `media` hold `events: owner` and no `events: manage`.
2. Log in as a Mídia user; `POST /ipbcb/api/admin/events/` (multipart) with `title`,
   `start_date` = today, a 1920×1080 JPEG → `201`.
3. Without a token: `GET /ipbcb/api/events/` lists it; its `image_url` loads with no token.
4. `PATCH` it to `visibility=members` → anonymous list is empty, the detail and `image_url` are
   `404`; as a member both work.
5. `PATCH` a 4:3 image → `400` with `field_errors.image`.
6. `GET /ipbcb/api/admin/events/?status=past` → empty; set `start_date`/`end_date` to yesterday →
   the event moves to `past` and leaves the public list.
7. As Liderança, `DELETE` it → `204`; the image file is gone from `media/events/`.

Contract details: [contracts/events-api.md](contracts/events-api.md). Model:
[data-model.md](data-model.md).

## Deploy notes

- No nginx change: `events/` goes through the existing media proxy and `protected-media` alias.
- The app must ship its tokenless image loader before visitors can see images (app side, already
  agreed).
- Verify `core.0008` against a restored production dump and run its reverse once (CLAUDE.md §5,
  as for 0006).
