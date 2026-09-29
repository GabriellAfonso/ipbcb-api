# Contract: Gallery API

All routes under `/ipbcb/`. Errors use the canonical `{"error_code", "detail"}` body. `401`
unauthenticated, `403 PERMISSION_DENIED` when the caller lacks membership (reads) or the level
on `gallery` (writes). Permission is checked before existence, so a caller without access gets
`403` for a nonexistent id too.

"member" = `IsMemberUser`. "manage" / "owner" = level on scope `gallery` (Admin, Liderança and
Mídia all hold `owner`).

## Resources

**Album**

```json
{"id": 7, "name": "Retiro 2026", "parent_id": 2, "description": "", "event_date": null,
 "cover_url": "https://host/ipbcb/media/gallery/covers/9/3f2a….jpg", "cover_source_album_id": 9}
```

**Photo**

```json
{"id": 1, "name": "IMG_0042.jpg", "description": "", "album_id": 7, "album_name": "Retiro 2026",
 "image_url": "https://host/ipbcb/media/gallery/7/9b1e….jpg",
 "thumbnail_url": "https://host/ipbcb/media/gallery/thumbs/7/c4d0….jpg",
 "date_taken": "2026-03-14", "uploaded_at": "2026-03-15T10:00:00Z"}
```

`thumbnail_url` is `null` for a photo not yet backfilled. `uploaded_by` never appears.

## Albums

### GET /api/albums/ — member

`200` — array of Album, tree order (pre-order DFS, siblings by position then id).

### POST /api/albums/ — manage

```json
{"name": "Retiro 2026", "parent_id": 2, "description": "", "event_date": "2026-03-14"}
```

Only `name` is required. `201` — Album. `400` blank name, duplicate sibling name
(`VALIDATION_ERROR`, Portuguese detail). `404` unknown `parent_id`.

### PATCH /api/albums/{id}/ — manage

Any subset of `name`, `parent_id` (`null` = move to root), `description`, `event_date` (`null`
clears). `200` — Album. Moving appends to the new siblings; same parent keeps the position.
`400` duplicate sibling name; `400` cycle:

```json
{"error_code": "VALIDATION_ERROR",
 "detail": "Não é possível mover o álbum 3 para dentro do álbum 9: 9 está dentro de 3.",
 "album_id": 3, "parent_id": 9, "chain": [9, 5, 3]}
```

`404` unknown album or `parent_id`.

### PUT /api/albums/order/ — manage

```json
{"parent_id": null, "ids": [5, 1, 3]}
```

`204`. `ids` must be exactly the current children of `parent_id` (roots when `null`). Otherwise
`400`:

```json
{"error_code": "VALIDATION_ERROR",
 "detail": "Order must list every sibling exactly once: missing [4], unexpected [8], repeated [1].",
 "missing": [4], "unexpected": [8], "repeated": [1]}
```

`404` unknown `parent_id`.

### PUT /api/albums/{id}/cover/ — manage

Multipart, one file in field `image`. Same validation as photo upload plus the 50 MP limit;
stored as the 1000×1000 center-cropped JPEG. `200` — Album. `400` missing file, invalid image
(Portuguese detail from `core.files.image_validation`), too many pixels, unprocessable; the
previous cover stays. `404` unknown album.

### DELETE /api/albums/{id}/cover/ — owner

`204`, also when the album had no own cover. The file is deleted after commit. No cover is
regenerated. `404` unknown album.

## Photos

### GET /api/photos/ — member *(existing, extended)*

`200` — array of Photo, by album tree order, then position, then id.

### GET /api/albums/{id}/photos/ — member *(existing, changed)*

`200` — array of Photo directly in the album, by position then id. **`404` for an unknown
album** (was `200 []`).

### POST /api/photos/ — manage

Multipart: `album_id` + one or more files in field `image`.

| Outcome | Status | Body |
|---------|--------|------|
| all accepted | `201` | `{"accepted": [Photo…], "rejected": []}` |
| partial | `207` | `{"accepted": [Photo…], "rejected": [{"filename", "reason"}…]}` |
| none accepted | `400` | `{"error_code": "VALIDATION_ERROR", "detail": "Nenhuma imagem foi aceita.", "rejected": [{"filename", "reason"}…]}` |
| no `album_id` / non-integer / no file | `400` | canonical, no `rejected` |
| unknown album | `404` | canonical |

Per-file reasons (Portuguese): size, format (both from `core.files.image_validation`), pixel
limit, and "could not be processed" (thumbnail failure). Accepted photos: `name` = filename,
`description` empty, `date_taken` from EXIF or `null`, last position in the album, thumbnail
present. The album gets an automatic cover from the first accepted file when it had no photos
and no own cover.

#### `client_upload_id` *(added by `specs/016-photo-upload-idempotency/`)*

Optional multipart field: 1–64 characters of `A-Z a-z 0-9 - _` (a canonical UUID v4 fits), sent
once, with exactly one file; compared exactly; never returned in any resource.

| Case | Status | Body |
|------|--------|------|
| no `client_upload_id` | as above | as above |
| id not stored on any photo | as above | as above; the photo now carries the id |
| id stored on a live photo | `201` | `{"accepted": [Photo], "rejected": []}` — the photo as it is now, possibly in another album |
| id stored on a trashed photo | `409` | canonical `CONFLICT`, `client_upload_id` |
| id empty, over 64 characters or another character | `400` | canonical, `client_upload_id` (cut at 64), `expected` |
| id with 2+ files | `400` | canonical, `file_count` (0 files keeps the message above) |
| id sent twice | `400` | canonical |

With an id already stored, `album_id` is checked for presence and integer form only — never
looked up — and the file is not examined. Permission comes first (`403`).

```json
{"error_code": "CONFLICT",
 "detail": "Esta foto já foi enviada e depois apagada; ela está na lixeira.",
 "client_upload_id": "3f2a9c1e-7b4d-4e8a-9f10-2c6b5d7e8a90"}
```

```json
{"error_code": "VALIDATION_ERROR",
 "detail": "Field 'client_upload_id' must be 1-64 characters of A-Z, a-z, 0-9, '-' or '_'; got 70 characters.",
 "client_upload_id": "…first 64 characters…",
 "expected": "1-64 characters of A-Z, a-z, 0-9, '-' or '_'"}
```

```json
{"error_code": "VALIDATION_ERROR",
 "detail": "Field 'client_upload_id' identifies one photo; send exactly one file in 'image', got 3.",
 "file_count": 3}
```

Shape messages are in English (client developers); the trashed message is in Portuguese (shown
to the user). Logs, ids only: `gallery_upload_deduplicated` and `gallery_upload_original_trashed`,
each with `photo_id` and `actor_id`.

### PATCH /api/photos/{id}/ — manage

Any subset of `name` (1–100), `description`, `date_taken` (`null` clears), `album_id`. Other
keys (`image`, `thumbnail`, …) are rejected with `400`. Moving appends to the target album;
files do not move. `200` — Photo. `404` unknown photo or `album_id`.

### PUT /api/albums/{id}/photos/order/ — manage

```json
{"ids": [12, 10, 11]}
```

`204`. Same exact-set rule and `400` body as album order. `404` unknown album.
