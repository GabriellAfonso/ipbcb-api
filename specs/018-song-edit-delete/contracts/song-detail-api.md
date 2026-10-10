# Contract: `api/songs/{id}/`

Base path `/ipbcb/`. JSON in and out. Errors use the canonical shape
`{"error_code", "detail", ...extra}` (constitution, Error shape).

Permission: `IsAuthenticated` + `scope_permission(Scope.SONGS)`, no override.

| Method | Level |
|--------|-------|
| `PATCH` | `manage` |
| `DELETE` | `owner` |

Any other method answers `405`.

---

## PATCH `api/songs/{id}/`

### Request

Any non-empty subset of:

```json
{ "title": "Oceans", "artist": "Hillsong", "youtube_link": "https://youtu.be/xxxx" }
```

| Field | Rule |
|-------|------|
| `title` | string, trimmed, 1–100 characters |
| `artist` | string, trimmed, 1–100 characters |
| `youtube_link` | string, trimmed, `""` (clears) or an http(s) URL of at most 200 characters, stored as sent |

An omitted field is unchanged. `null` is invalid. Any other key is invalid.

### Responses

**200**: the song, in the same shape as an item of `GET api/songs/`:

```json
{ "id": 42, "title": "Oceans", "artist": "Hillsong", "category": "Worship", "youtube_link": "" }
```

`category` is the category name, or `""` when there is none.

**400 `VALIDATION_ERROR`**: empty body, unknown key, `null`, empty/too-long text, or a bad URL:

```json
{
  "error_code": "VALIDATION_ERROR",
  "detail": "Validation failed.",
  "field_errors": { "category": ["Extra inputs are not permitted"] }
}
```

**409 `CONFLICT`**: only when the edit changes the normalized title + artist pair, and another song
already has the resulting pair (case-insensitive):

```json
{
  "error_code": "CONFLICT",
  "detail": "Song already exists: title='Oceans', artist='Hillsong'",
  "title": "Oceans",
  "artist": "Hillsong"
}
```

**404 `NOT_FOUND`**: no song with that id:

```json
{ "error_code": "NOT_FOUND", "detail": "Song not found: id=999", "song_id": 999 }
```

**401** no or invalid token · **403** below `manage` on `songs`.

---

## DELETE `api/songs/{id}/`

No body.

### Responses

**204**: deleted, with an empty body. The song's chord charts and lyrics are deleted with it.

**409 `CONFLICT`**: the song has plays and/or is on a saved setlist. Nothing is deleted.

```json
{
  "error_code": "CONFLICT",
  "detail": "A música \"Oceans\" não pode ser excluída: foi tocada em 7 domingos e está na setlist de 18/10/2026.",
  "song_id": 42,
  "title": "Oceans",
  "plays": 7,
  "setlist_dates": ["2026-10-18"]
}
```

Wording of `detail`:

| plays | setlist_dates | detail after the `: ` |
|-------|---------------|-----------------------|
| 1 | `[]` | `foi tocada em 1 domingo.` |
| 7 | `[]` | `foi tocada em 7 domingos.` |
| 0 | `["2026-10-18"]` | `está na setlist de 18/10/2026.` |
| 0 | two or more dates | `está nas setlists de 18/10/2026 e 25/10/2026.` (three or more: `A, B e C`) |
| 7 | `["2026-10-18"]` | `foi tocada em 7 domingos e está na setlist de 18/10/2026.` |

`plays` counts distinct play dates. `setlist_dates` are distinct and ascending. The same shape is
returned when the reference appeared between the check and the delete.

**404 `NOT_FOUND`**: as for PATCH.

**401** no or invalid token · **403** below `owner` on `songs` (a Liderança user included).
