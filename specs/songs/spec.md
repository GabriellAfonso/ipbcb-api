# Songs Domain Spec

## Purpose

Manages worship songs, play history, hymnal, chord charts, and lyrics for the church app. Provides song suggestions based on play history and supports registering which songs were played each Sunday. Also collects passive hymnal usage history from the app, so the church can see which hymns the congregation actually opens and sings.

> **Implementation status**: everything below is implemented. Service windows moved to the shared catalogue `core.ChurchService` in feature 007 — see `specs/006-hymnal-view-history/` and `specs/007-unify-service-catalogue/`.

---

## Data Models

### Category

| Field | Type        | Constraints   |
|-------|-------------|---------------|
| name  | CharField   | max=100, unique |

### Song

| Field        | Type         | Constraints                  |
|--------------|--------------|------------------------------|
| title        | CharField    | max=100                      |
| artist       | CharField    | max=100                      |
| category     | FK(Category) | nullable, SET_NULL           |
| youtube_link | URLField     | max=200, blank, default=""   |

### Played

| Field    | Type       | Constraints                      |
|----------|------------|----------------------------------|
| song     | FK(Song)   | nullable, blank, PROTECT         |
| tone     | CharField  | max=3                            |
| position | IntegerField |                                |
| date     | DateField  |                                  |

### Hymn

| Field  | Type       | Constraints         |
|--------|------------|---------------------|
| number | CharField  | max=10, unique (accepts alphanumeric like "110-A") |
| title  | CharField  | max=200             |
| lyrics | JSONField  |                     |

### ChordChart

| Field      | Type         | Constraints                        |
|------------|--------------|-------------------------------------|
| song       | FK(Song)     | CASCADE                            |
| content    | TextField    |                                    |
| tone       | CharField    | max=3, blank                       |
| instrument | CharField    | max=50, blank                      |
| created_at | DateTimeField| auto_now_add                       |
| updated_at | DateTimeField| auto_now                           |

**unique_together**: (song, tone, instrument)

### Lyrics

| Field      | Type           | Constraints  |
|------------|----------------|--------------|
| song       | OneToOne(Song) | CASCADE      |
| content    | TextField      |              |
| created_at | DateTimeField  | auto_now_add |
| updated_at | DateTimeField  | auto_now     |

### HymnalViewEvent

One row per hymn view the app counted as real. Passive telemetry — not the official repertoire.

| Field            | Type          | Constraints                            |
|------------------|---------------|----------------------------------------|
| client_event_id  | UUIDField     | unique — idempotency key from the app  |
| hymn             | FK(Hymn)      | required, PROTECT                      |
| user             | FK(User)      | nullable, blank, SET_NULL (anonymous)  |
| device_id        | CharField     | required — one UUID per app install    |
| viewed_at        | DateTimeField | timezone-aware, sent by the app        |
| duration_seconds | PositiveIntegerField |                                 |
| app_version      | CharField     | blank                                  |
| platform         | CharField     | blank                                  |
| created_at       | DateTimeField | auto_now_add — when the server received it |

### Service windows — now `core.ChurchService`

`ServiceWindow` was deleted by feature 007. The hymnal reads the church's service catalogue from `core.models.ChurchService`, shared with the `schedule` feature, which the constitution forbids importing directly.

**Weekday is `1 = Sunday … 7 = Saturday`** — one convention across the whole codebase, converted via `core/domain/weekday.py`. Sunday is `1`.

The catalogue also carries `takes_rota`, which the hymnal ignores: it separates "is held" from "members are scheduled for it", so Escola Bíblica Dominical groups hymn views without generating a rota.

### HymnalHistorySettings

Singleton (exactly one row, enforced) so an admin can tune collection without a deploy.

| Field                    | Type                 | Default |
|--------------------------|----------------------|---------|
| min_seconds_to_count     | PositiveIntegerField | 30      |
| collapse_window_minutes  | PositiveIntegerField | 10      |
| max_batch_size           | PositiveIntegerField | 200     |
| max_past_days            | PositiveIntegerField | 90      |
| future_tolerance_minutes | PositiveIntegerField | 5       |
| window_grace_minutes     | PositiveIntegerField | 30      |

---

## Endpoints

All endpoints are prefixed with the base path (`/ipbcb/`).

### GET /api/songs/

List all songs with category name.

- **Auth**: AllowAny
- **Response**: `200` with ETag support (304 if unchanged)
- **Response body**: array of `{ id, title, artist, category }`
- **Ordering**: title, artist

### GET /api/songs-by-sunday/

List all plays grouped by date.

- **Auth**: AllowAny
- **Response**: `200` with ETag support
- **Response body**: array of `{ date, songs: [{ song_id, position, song, artist, tone }] }`
- **Ordering**: date desc, position asc
- **Date format**: `dd/mm/yyyy`

### GET /api/top-songs/

Most played songs ranked by play count.

- **Auth**: AllowAny
- **Response**: `200` with ETag support
- **Response body**: array of `{ song_id, song__title, play_count }`

### GET /api/top-tones/

Most used tones ranked by count.

- **Auth**: AllowAny
- **Response**: `200` with ETag support
- **Response body**: array of `{ tone, tone_count }`

### GET /api/suggested-songs/

Suggest songs for positions 1-4. Excludes songs played in the last 90 days.

- **Auth**: AllowAny
- **Query params**:
  - `fixed` (optional): pin specific positions. Format: `"1:12,3:45"` (position:played_id)
- **Response**: `200`
- **Response body**: array of serialized Played objects with overridden position

**Business rules**:
- Only suggests songs not played in last 90 days
- Matches songs to their historical position
- No duplicate songs across positions
- Fixed positions are respected (pinned by Played id)
- Positions limited to 1-4

### GET /api/hymnal/

List all hymns ordered by number (numeric sort, with alphanumeric suffix support).

- **Auth**: AllowAny
- **Response**: `200` with ETag support
- **Response body**: array of `{ id, number, title, lyrics }`
- **`id` is required by the app**, not decorative: the hymn view history ingest endpoint keys events on `hymn_id`. `number` is a string and cannot substitute for it, so without `id` the app cannot build a valid view event at all.
- **Note**: Ordering is done in Python (`hymn_numbering.hymn_sort_key`), not in SQL, so the endpoint works on any database backend

### POST /api/played/register/

Register songs played on a given Sunday.

- **Auth**: `IsAuthenticated` + `scope_permission(Scope.SONGS)` — `manage` (Admin, Liderança; `specs/012-feature-role-permissions/`)
- **Request body**:
  ```json
  {
    "date": "2026-02-07",
    "plays": [
      { "song_id": 12, "position": 1, "tone": "G" }
    ]
  }
  ```
- **Validation**:
  - `date` required, format YYYY-MM-DD
  - `plays` required, non-empty list
  - Each play: `song_id` and `position` required integers
  - Position range: 1-10 (allows extra songs for special occasions)
  - All referenced songs must exist
- **Response**: `201 { "created": N }` on success
- **Errors**: `400 { "detail": "..." }` with descriptive messages

### GET /api/chord-charts/

List all chord charts ordered alphabetically by song title.

- **Auth**: AllowAny
- **Response**: `200`
- **Response body**: array of `{ id, song_id, content, tone, instrument, updated_at }`
- **Ordering**: song title (ascending)

### POST /api/chord-charts/

Create a new chord chart for a song.

- **Auth**: `IsAuthenticated` + `scope_permission(Scope.SONGS)` — `manage`. `PATCH /api/chord-charts/{id}/` (edit `content`) requires the same
- **Request body**: `{ song_id, content, tone, instrument }` — all required
- **Response**: `201` with `{ id, song_id, content, tone, instrument, updated_at }`
- **Errors**: `400` if song_id not found, or any required field missing/empty

### GET /api/lyrics/

List all lyrics ordered alphabetically by song title.

- **Auth**: AllowAny
- **Response**: `200`
- **Response body**: array of `{ id, song_id, content, updated_at }`
- **Ordering**: song title (ascending)

### POST /api/lyrics/

Create lyrics for a song.

- **Auth**: `IsAuthenticated` + `scope_permission(Scope.SONGS)` — `manage`. `PATCH /api/lyrics/{id}/` (edit `content`) requires the same
- **Request body**: `{ song_id, content }` — all required
- **Response**: `201` with `{ id, song_id, content, updated_at }`
- **Errors**: `400` if song_id not found or content empty

---

## Hymnal View History Endpoints

Passive usage telemetry for the hymnal. Separate from `Played` / `RegisterSundayPlaysAPI`, which stays untouched: that one points to `Song` and is registered manually by an admin; this one points to `Hymn` and is collected by the app.

All timestamp reasoning uses `America/Sao_Paulo`.

### POST /api/hymnal-history/events/

Ingest a batch of view events. The app buffers offline and syncs when it has network.

- **Auth**: AllowAny, throttled
- **Request body**: list of `{ client_event_id, hymn_id, device_id, viewed_at, duration_seconds, app_version?, platform? }`
- **User attribution**: a valid JWT associates the events to that user; otherwise `user` stays null. `device_id` is required either way.
- **Response**: `201 { "accepted": ["<client_event_id>"], "rejected": [{ "client_event_id", "reason" }] }`
- **Per-event rules**:
  - Idempotency — an existing `client_event_id` creates nothing and still returns in `accepted`
  - Write-time collapse — an event for the same hymn + device within `collapse_window_minutes` of `viewed_at` is discarded and returned in `accepted`
  - Unknown `hymn_id` → `rejected`
  - `viewed_at` beyond now + `future_tolerance_minutes`, or older than `max_past_days` → `rejected`
  - `duration_seconds` is **not** re-validated against `min_seconds_to_count` — that threshold is client-side, and buffered events may carry an older value
- **Errors**: `400` for the whole request when the batch exceeds `max_batch_size`
- **Partial batches must work** — one bad event never blocks the rest. `accepted` means "safe to delete locally" (stored, duplicated or collapsed alike); `rejected` events are also deleted, with the reason logged, so nothing retries forever.

### GET /api/hymnal-history/occurrences/

Dashboard by period — covers week, month, year and any custom range.

- **Auth**: `IsAuthenticated` + `scope_permission(Scope.REPORTS_HYMNAL_HISTORY)` — `view` (Admin, Liderança, Mídia)
- **Query params**: `from` (date), `to` (date), `group_by` = `service` | `day` | `week` | `month`
- **Response**: `200` — the occurrences in the range, each with the hymn number and title, its grouping bucket, and how many distinct devices contributed

**Occurrence rule**: an occurrence is a hymn sung *once by the congregation*, not once per person. Collapsing key is hymn + church service; events matching no active window collapse by hymn + calendar day. A window matches from `start_time` until `end_time` plus `window_grace_minutes`, because services run long — the start is never extended. Occurrences are derived at read time, so changing a window or the grace never rewrites stored events.

### GET /api/hymnal-history/top-hymns/

Ranking / chart data — X is the hymn number, Y is how many times it was sung.

- **Auth**: `IsAuthenticated` + `scope_permission(Scope.REPORTS_HYMNAL_HISTORY)` — `view` (Admin, Liderança, Mídia)
- **Query params**: `from` (optional), `to` (optional) — default is all time
- **Response**: `200` — only hymns with at least one occurrence, ordered by count descending. Counts occurrences (collapsed), not raw events.

### GET /api/hymnal-history/settings/

- **Auth**: AllowAny — the app reads `min_seconds_to_count` on startup before anyone logs in
- **Response**: `200` with the singleton values

### PATCH /api/hymnal-history/settings/

- **Auth**: `IsAuthenticated` + `scope_permission(Scope.REPORTS_HYMNAL_HISTORY, {"PATCH": owner})` — `owner` by override: configuration is Admin-only
- **Validation**: every field a positive integer within a sane upper bound
- **Response**: `200` with the updated values
- **Errors**: `400` naming the field, the offending value and the accepted range
- Changing a setting affects future behaviour only — it never rewrites stored history.

### CRUD /api/hymnal-history/service-windows/

- **Auth**: `IsAuthenticated` + `scope_permission(Scope.REPORTS_HYMNAL_HISTORY)`. Reads (`GET` list and detail) `view`; `POST` and `PATCH` `owner` by override; `DELETE` `owner` by default — configuration writes are Admin-only
- List, create, update and delete service windows from the app
- **Validation**: `end_time` strictly after `start_time`, `weekday` in 0-6

---

## Architecture

Follows clean architecture (Views -> Services -> Repositories -> Models):

- **Repository**: `SongRepositoryImpl` (songs, played, chord charts, lyrics), `HymnalRepositoryImpl` (hymns)
- **Services**: `SongService` (queries + suggestions), `RegisterPlaysService` (play registration), `HymnalService` (hymnal listing)
- **DI**: All services/repositories registered in `config/di.py`, injected via `@inject` + `Provide[Container.xxx]`

Hymnal view history follows the same pattern — its own repositories for view events, service windows and settings, its own services for ingest and for occurrence reporting, Pydantic DTOs between layers, domain exceptions from `core/domain/exceptions.py`, and DI registration in `config/di.py`. Component names and implementation order are defined in `specs/006-hymnal-view-history/plan.md`.

---

## Design Decisions

- **Position 1-4 vs 1-10**: Normal service has 4 songs (positions 1-4). `SuggestedSongsAPI` only suggests for 1-4. `RegisterSundayPlaysAPI` accepts up to 10 for special occasions. This is intentional.
- **AllowAny on most endpoints**: Internal church app, no sensitive data. Only the management writes (plays, chord charts, lyrics) and the hymnal history reports and configuration require a scope level (`specs/012-feature-role-permissions/`).
- **ETag caching**: Read-only list endpoints use SHA-256 ETag for conditional GET (304 Not Modified).
- **Random suggestion**: `random.choice` for song selection — simple and adequate for the use case.
- **View history lives in `songs`, not a new app**: `Hymn` lives here and the constitution forbids features importing from each other. The service catalogue was briefly duplicated here for the same reason, then moved to `core.ChurchService` in feature 007 so both features could share one source of truth.
- **`Played` vs `HymnalViewEvent`**: intentionally separate. `Played` is the official Sunday repertoire (`Song`, manual, admin). `HymnalViewEvent` is passive usage telemetry (`Hymn`, automatic, app). They coexist and never share models.
- **AllowAny + throttle on ingest**: this is the only *write* endpoint open to unauthenticated clients. Most members use the hymnal without logging in, so requiring auth would collect a biased and largely empty history. Compensating controls: throttling, a required `device_id`, the `client_event_id` idempotency key, and strict per-event validation. The data carries nothing sensitive.
- **Client-side duration threshold**: `min_seconds_to_count` is enforced by the app, never re-checked on ingest. A device syncing buffered events may still hold an older config value, and rejecting those would silently drop legitimate history.
- **No confirmation endpoint**: `client_event_id` gives real idempotency, so the app just re-sends instead of asking the server what it already has.
- **Occurrences derived at read time**: never materialized. Editing service windows changes future reports without touching a single stored event.
