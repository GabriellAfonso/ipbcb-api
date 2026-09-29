# Contract: Photo Upload with a Client Upload Id

Delta over `POST /api/photos/` in `specs/013-gallery-write-api/contracts/gallery-api.md`, which
gains this section at implementation (spec FR-020). Everything not listed here is unchanged.

## POST /api/photos/ — manage

Multipart: `album_id` + one or more files in field `image` + optional `client_upload_id`.

### `client_upload_id`

- 1–64 characters, ASCII letters, digits, `-`, `_`. A canonical UUID v4
  (`"3f2a9c1e-7b4d-4e8a-9f10-2c6b5d7e8a90"`) fits.
- Sent once per request, with exactly one file.
- Compared exactly (case-sensitive). Never returned in any resource.

### Outcomes

| Case | Status | Body |
|------|--------|------|
| no `client_upload_id` | as in 013 | as in 013 |
| id not stored on any photo | as in 013 (`201` / `400`) | as in 013; the photo now carries the id |
| id stored on a live photo | `201` | `{"accepted": [Photo], "rejected": []}` — the photo as it is now, possibly in another album |
| id stored on a trashed photo | `409` | canonical, see below |
| id empty, over 64 characters or with another character | `400` | canonical, see below |
| id with 0 or 2+ files | `400` | canonical, see below (0 files keeps the 013 message) |
| id sent twice | `400` | canonical |

With an id stored on a photo, `album_id` is checked for presence and integer form only: an
unknown or trashed `album_id` does not turn the repeat into a `404`, and the file is not
examined. Permission is checked first (`403`), as today.

### Bodies

Deduplicated (same shape and status as a first upload):

```json
{"accepted": [{"id": 41, "name": "IMG_0042.jpg", "description": "", "album_id": 9,
               "album_name": "Retiro 2026", "image_url": "https://host/ipbcb/media/gallery/7/9b1e….jpg",
               "thumbnail_url": "https://host/ipbcb/media/gallery/thumbs/7/c4d0….jpg",
               "date_taken": "2026-03-14", "uploaded_at": "2026-03-15T10:00:00Z",
               "position": 3, "members": []}],
 "rejected": []}
```

Trashed original:

```json
{"error_code": "CONFLICT",
 "detail": "Esta foto já foi enviada e depois apagada; ela está na lixeira.",
 "client_upload_id": "3f2a9c1e-7b4d-4e8a-9f10-2c6b5d7e8a90"}
```

Malformed id:

```json
{"error_code": "VALIDATION_ERROR",
 "detail": "Field 'client_upload_id' must be 1-64 characters of A-Z, a-z, 0-9, '-' or '_'; got 70 characters.",
 "client_upload_id": "3f2a9c1e-7b4d-4e8a-9f10-2c6b5d7e8a90-3f2a9c1e-7b4d-4e8a-9f10-2c6b5d7e",
 "expected": "1-64 characters of A-Z, a-z, 0-9, '-' or '_'"}
```

(`detail` names the first offending character instead, e.g. `got ' ' at position 8.`; the echoed
value is cut at 64 characters.)

Id with several files:

```json
{"error_code": "VALIDATION_ERROR",
 "detail": "Field 'client_upload_id' identifies one photo; send exactly one file in 'image', got 3.",
 "file_count": 3}
```

Id sent twice:

```json
{"error_code": "VALIDATION_ERROR",
 "detail": "Field 'client_upload_id' must be sent at most once, got 2 values."}
```

Malformed-id messages are in English (client developers); the trashed-original message is in
Portuguese (shown to the user).

### Logs *(spec 002 format, ids only)*

| Event | Fields | When |
|-------|--------|------|
| `gallery_upload_deduplicated` | `photo_id`, `actor_id` | answered with a live original, fast path or lost race |
| `gallery_upload_original_trashed` | `photo_id`, `actor_id` | answered `409` |
