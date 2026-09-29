# Contract: Gallery Trash and Change Feed

Additions to `specs/013-gallery-write-api/contracts/gallery-api.md`. Base path `/ipbcb/`,
JWT in `Authorization: Bearer`. Every error is the canonical `{"error_code", "detail"}`
(spec 001), sometimes with extra fields as listed. `401` for a missing or invalid token applies
to every route and is not repeated.

---

## Changes to existing resources

Album and Photo resources gain `position` (integer) as their last field, on every endpoint that
returns them. Nothing else changes.

```json
{ "id": 7, "name": "Retiro 2026", "parent_id": 2, "description": "", "event_date": null,
  "cover_url": null, "cover_source_album_id": null, "position": 3 }
```

Trashed albums and photos are absent from `GET /api/albums/`, `GET /api/photos/` and
`GET /api/albums/{id}/photos/`. Every 013 route that names a trashed item in its path or body
answers `404`, as for an unknown id. In an order request, a trashed id is reported in
`unexpected`.

---

## DELETE /api/albums/{id}/

Permission: `owner` on `gallery`.

| Case | Status | Body |
|------|--------|------|
| trashed with its subtree | `204` | empty |
| unknown or already trashed | `404` | `NOT_FOUND`, `album_id` |
| no `owner` on `gallery` | `403` | `PERMISSION_DENIED` (checked before existence) |

## DELETE /api/photos/{id}/

Same as above, with `photo_id`.

---

## GET /api/gallery/trash/

Permission: `owner` on `gallery` (override of `GET`).

`200`, ordered by `deleted_at` descending, then `id`:

```json
[
  {
    "kind": "album",
    "id": 7,
    "name": "Retiro 2026",
    "deleted_at": "2026-09-29T14:03:11Z",
    "deleted_by": "Maria Souza",
    "uploaded_by": null,
    "purge_on": "2026-10-29",
    "sub_album_count": 2,
    "photo_count": 41,
    "thumbnail_url": "http://host/ipbcb/media/gallery/covers/7/3f2a….jpg"
  },
  {
    "kind": "photo",
    "id": 301,
    "name": "IMG_0042.jpg",
    "deleted_at": "2026-09-28T09:12:00Z",
    "deleted_by": "João Lima",
    "uploaded_by": "Ana Paula",
    "purge_on": "2026-10-28",
    "sub_album_count": 0,
    "photo_count": 0,
    "thumbnail_url": "http://host/ipbcb/media/gallery/thumbs/7/c4d0….jpg"
  }
]
```

- One entry per deletion batch; albums and photos that went with an album entry are not listed.
- `deleted_by`, `uploaded_by`: display name or `null`. `uploaded_by` is always `null` for albums.
- `purge_on`: date (UTC) of `deleted_at + 30 days`; the item is purged on the first daily run
  on or after it.
- `thumbnail_url`: readable by the caller (they hold `owner`), `null` when there is no file.
- Empty trash: `200 []`.

---

## POST /api/gallery/trash/albums/{id}/restore/

Permission: `owner` on `gallery` (override of `POST`). No body.

| Case | Status | Body |
|------|--------|------|
| restored with its batch | `200` | Album resource |
| not in the trash (live, unknown, purged) or not the root of its batch | `404` | `NOT_FOUND`, `kind: "album"`, `id` |
| its parent is in the trash | `400` | `VALIDATION_ERROR`, `kind`, `id`, `trashed_parent_id` |
| a live sibling holds its name | `400` | `VALIDATION_ERROR`, `album_id`, `name`, `conflicting_album_id` |

Examples of `detail` (Portuguese, user-facing):

```json
{ "error_code": "VALIDATION_ERROR",
  "detail": "Não é possível restaurar o álbum 7 ('Culto'): o álbum 12 já usa esse nome no mesmo lugar. Renomeie-o antes.",
  "album_id": 7, "name": "Culto", "conflicting_album_id": 12 }
```

```json
{ "error_code": "VALIDATION_ERROR",
  "detail": "Não é possível restaurar o álbum 9: o álbum 7, onde ele ficava, está na lixeira. Restaure o álbum 7 primeiro.",
  "kind": "album", "id": 9, "trashed_parent_id": 7 }
```

Nothing is restored on any refusal.

## POST /api/gallery/trash/photos/{id}/restore/

Same shape, `200` with the Photo resource. A photo trashed as part of an album's batch is `404`
here: it comes back only with its album. `TrashedParentError` names the photo's album. There is
no name conflict for photos.

---

## GET /api/gallery/changes/?since={cursor}

Permission: member (`IsMemberUser`).

`200` always, for any `since`:

```json
{
  "albums": [ { "...": "Album resource" } ],
  "photos": [ { "...": "Photo resource" } ],
  "deleted_album_ids": [12, 13],
  "deleted_photo_ids": [301, 302, 305],
  "cursor": "v1.AAYh3k9x2QA",
  "full_sync_required": false
}
```

| `since` | `albums`, `photos` | deleted lists | `full_sync_required` |
|---------|--------------------|---------------|----------------------|
| absent | every live item, like the list endpoints | `[]` | `false` |
| valid, within 90 days | items created or changed after `since − 90 s` | ids deleted after `since − 90 s` and not restored | `false` |
| older than 90 days, unreadable, future, unknown version | `[]` | `[]` | `true` |

- **Cursor**: store it and send it back verbatim. Never parse it.
- **Duplicates**: an item changed shortly before the cursor was issued may come again in the
  next answer. Apply both lists idempotently: upsert `albums`/`photos` by id, remove the deleted
  ids.
- **Changed** includes derived fields: a photo whose album was renamed (`album_name`), an album
  whose resolved cover changed, and any item whose `position` changed.
- **Deleted** includes photos trashed with their album. A restored item reappears in `albums` or
  `photos` and leaves the deleted lists.
- **`full_sync_required: true`**: fetch `GET /api/albums/` and `GET /api/photos/`, replace the
  local copy with them (drop every local id missing from them), then use the returned cursor.
- Order: `albums` in tree order, `photos` by their album's tree order, then `position`, then
  `id`, the same as the list endpoints.
- Non-member: `403`.

---

## Media (`/ipbcb/media/gallery/...`), amended from spec 009

| Caller | File of a trashed item | Any other `gallery/` file |
|--------|------------------------|---------------------------|
| member without `owner` on `gallery` | `404` | as 009 (`200` + redirect, or `404` if missing) |
| member with `owner` | as 009 | as 009 |
| `owner`, not member | as 009 | `403` (unchanged) |
| neither | `403` | `403` |

"File of a trashed item" means the `image` or `thumbnail` of a trashed photo, including a photo
trashed with its album, or the `cover_image` of a trashed album. Old paths
(`gallery/{slug}/{filename}`) are included. Files that no row references keep 009's behaviour.
Paths outside `gallery/` are unaffected.

---

## Management command

```
python manage.py purge_gallery_trash
```

Output: one plain line, e.g.
`purged 3 batches (2 albums, 45 photos); skipped 1: [9b1e…]; expired 12 marks`.
Exit code `0` even when batches were skipped (retried on the next run). Idempotent.
