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

### Setlist

The Sunday repertoire chosen in advance by the worship ministry — what *will* be played.
`Played` stays the record of what *was* played. Design in `specs/017-sunday-setlist-push/`.

| Field              | Type          | Constraints                                               |
|--------------------|---------------|-----------------------------------------------------------|
| date               | DateField     | unique — always a Sunday (checked by the service)         |
| saved_by           | FK(User)      | nullable, SET_NULL — last author                          |
| saved_at           | DateTimeField | set on every save                                         |
| last_reminder_slot | DateTimeField | nullable — start of the last reminder window claimed; a re-save never resets it |

### SetlistItem

| Field    | Type                      | Constraints                                  |
|----------|---------------------------|----------------------------------------------|
| setlist  | FK(Setlist)               | CASCADE, `related_name="items"`              |
| position | PositiveSmallIntegerField | 1-10, unique per setlist                     |
| song     | FK(Song)                  | PROTECT — a song in any setlist cannot be deleted |
| tone     | CharField                 | max=3, required                              |

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
- **Errors**:
  - `400` (`VALIDATION_ERROR`) for a malformed body, a missing or invalid field, or a position
    out of range
  - `404` (`NOT_FOUND`, `SongsNotFoundError`) when any referenced song does not exist, listing
    the missing ids; nothing is created

### Setlist endpoints

Full contract (bodies, every error) in `specs/017-sunday-setlist-push/contracts/setlist-api.md`.
All private (`Cache-Control: private, no-store`, `Vary: Authorization`).

**Worship member**: a user whose profile is linked to a member of the ministry named "Louvor"
(case-insensitive, surrounding whitespace ignored; constant `core.domain.worship`). Ministry ids
are never used. `Member.is_active` is not considered. Membership never grants a scope level; it
only narrows who may save.

| Method | Path | Permission | Behaviour |
|--------|------|------------|-----------|
| PUT | `api/setlists/{date}/` | `manage` on `songs` **and** worship member | Create or fully replace the setlist of that Sunday. `items: [{song_id, position, tone}]`, non-empty, positions 1-10 unique, tone 1-3 chars. 400 non-Sunday / bad body / repeated positions, 403, 404 unknown songs (`missing_song_ids`). 200 with the stored setlist, then a `setlist_saved` push |
| GET | `api/setlists/{date}/` | `manage` on `songs` (`GET` override) | The setlist of that date, or 404 |
| DELETE | `api/setlists/{date}/` | `manage` on `songs` (`lowered` `DELETE`, spec 012) **and** worship member | Delete the setlist and its items; `Played` untouched. 204, 400 bad date, 403, 404 none for that date. No push |
| GET | `api/setlists/current/` | worship member (`IsWorshipMember`) | `{"setlist": ... }` — earliest date on or after today (`America/Sao_Paulo`), or `null` |
| GET | `api/setlists/pending-confirmation/` | `manage` on `songs` (`GET` override) | Setlists dated on or before today with no `Played` row for their date, newest first |

Setlist body: `{date, items: [{position, song_id, title, artist, tone}], saved_by_name, saved_at}`.

**Push after save**: data message `{"type": "setlist_saved", "date": "YYYY-MM-DD"}` to every
registered device of every worship member, author included, sent after the save commits. A push
failure is logged and never fails or rolls back the save. Tokens FCM reports as unregistered are
deleted.

### Reminder: `manage.py send_setlist_reminders`

Run every 60 s by the `ipbcb_setlist_reminder` loop in `compose.prod.yml`. On the setlist's
Sunday, from 21:00 `America/Sao_Paulo`, each half-hour window (21:00 … 23:30) sends one
`{"type": "confirm_plays", "date": ...}` push to the devices of users with `manage` on `songs` who
are worship members — only while no `Played` row exists for that date. The window is claimed on
the setlist row (`last_reminder_slot`, conditional update) before sending, so a restart, an
overlapping run or a failed send never repeats it; missed windows are never sent late. Prints one
summary line, always exits 0.

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
- List, create, update and delete rows of the shared catalogue `core.ChurchService` from the
  app (the route keeps its old "service-windows" name). Fields: `name`, `weekday`,
  `start_time`, `end_time`, `active` (default true), `takes_rota` (default true)
- **Validation**: `end_time` strictly after `start_time` (a PATCH is checked against the stored
  row), `weekday` in 1-7 (`1 = Sunday … 7 = Saturday`, same as everywhere else)

---

## Architecture

Follows clean architecture (Views -> Services -> Repositories -> Models):

- **Repository**: `SongRepositoryImpl` (songs, played, chord charts, lyrics), `HymnalRepositoryImpl` (hymns)
- **Services**: `SongService` (queries + suggestions), `RegisterPlaysService` (play registration), `HymnalService` (hymnal listing)
- **Setlists**: `SetlistRepositoryImpl`, `SetlistService` (save, current, by date, pending), `SetlistReminderService` (reminder run); push, device tokens and worship membership come from `core` (`PushService`, `WorshipAccessService`)
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
- **`Setlist` vs `Played`**: separate on purpose. The setlist is the plan, saved before the
  service by the worship ministry; `Played` is what happened, registered after. A `Played` row for
  the date — any row, matching the setlist or not — is what stops the reminder and clears the
  pending card.
- **Worship ministry by name**: ministry ids change when ministries are recreated in the admin,
  so "Louvor" is matched by name. Renaming it disables saving, distribution and reminders, which
  is logged as `worship_ministry_missing`.
- **Push is best effort**: the setlist is the source of truth; the app falls back to
  `api/setlists/current/` when a push never arrives.
- **Occurrences derived at read time**: never materialized. Editing service windows changes future reports without touching a single stored event.
