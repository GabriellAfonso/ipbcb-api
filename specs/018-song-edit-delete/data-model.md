# Data Model: Edit and Delete Songs

No model, field or migration changes. This feature adds behaviour over the existing schema
(`specs/songs/spec.md`, Data Models).

## Entities touched

| Entity | Role here | Relation to `Song` | On song delete |
|--------|-----------|--------------------|----------------|
| `Song` | edited (`title`, `artist`, `youtube_link`) or deleted | — | — |
| `Played` | blocks delete; counted by distinct `date` | `song` FK, `PROTECT`, `related_name="plays"` | refused |
| `SetlistItem` | blocks delete; reported by distinct `setlist.date` | `song` FK, `PROTECT`, `related_name="setlist_items"` | refused |
| `ChordChart` | removed with the song | `song` FK, `CASCADE` | deleted |
| `Lyrics` | removed with the song | `song` OneToOne, `CASCADE` | deleted |
| `Category` | read-only in the response | `Song.category` FK, `SET_NULL` | untouched |

## DTOs (`features/songs/dtos.py`)

### Shared field types

- `_SongText`: `str`, trimmed, 1–100 characters (already exists).
- `_YoutubeLink`: `str`, trimmed, at most 200 characters, `""` or an http(s) URL, stored as typed
  (new; extracted from `NewSongInput.youtube_link_is_url`).

### `NewSongInput` (existing, refactored)

Uses `_SongText` for `title` and `artist`, and `_YoutubeLink = ""` for the link. Behaviour is
unchanged.

### `SongChangesInput` (new)

| Field | Type | Rule |
|-------|------|------|
| `title` | `_SongText \| None = None` | explicit `null` → error on `title` |
| `artist` | `_SongText \| None = None` | explicit `null` → error on `artist` |
| `youtube_link` | `_YoutubeLink \| None = None` | explicit `null` → error; `""` clears |

- `extra="forbid"` (inherited from `StrictBaseModel`).
- At least one field present (`model_fields_set` non-empty), otherwise the error is at model level.
- The changes applied are `model_dump(exclude_unset=True)`.

### `SongUsage` (new)

| Field | Type | Meaning |
|-------|------|---------|
| `plays` | `int` | distinct dates with a `Played` row for the song |
| `setlist_dates` | `list[date]` | distinct `Setlist.date` of items holding the song, ascending |
| `in_use` (property) | `bool` | `plays > 0 or bool(setlist_dates)` |

## Domain exceptions (`core/domain/exceptions.py`)

| Exception | Base | HTTP | `extra_context()` |
|-----------|------|------|-------------------|
| `SongNotFoundError(song_id)` | `NotFoundError` | 404 | `{"song_id"}` |
| `SongInUseError(song_id, title, plays, setlist_dates)` | `ConflictError` | 409 | `{"song_id", "title", "plays", "setlist_dates"}` (ISO strings) |
| `DuplicateSongError(title, artist)` (existing) | `ConflictError` | 409 | `{"title", "artist"}` |

## State rules

- **Edit**: `found` → (pair changed? → duplicate check) → saved with `update_fields` limited to
  the fields sent.
- **Delete**: `found` → usage check → `in use` ⇒ `SongInUseError`; `free` ⇒ atomic delete
  (the cascade removes chord charts and lyrics). A late `ProtectedError` / `IntegrityError` ⇒
  re-read usage ⇒ `SongInUseError`, with nothing deleted.
