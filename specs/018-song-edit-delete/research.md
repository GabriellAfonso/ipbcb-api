# Research: Edit and Delete Songs

No `NEEDS CLARIFICATION` was left in the Technical Context: the stack, the layers and every
precedent already exist in `features/songs`. Each item below records a decision taken by reading
the current code.

## R-01 One set of field rules for create and edit

**Decision**: Move the `youtube_link` rule out of `NewSongInput`'s `field_validator` into a shared
`Annotated` type (`_YoutubeLink`, using an `AfterValidator`), next to the existing `_SongText`.
`NewSongInput` and the new `SongChangesInput` both declare their fields with these two types.

**Rationale**: FR-002 requires the rules to be defined once. `_SongText` is already shared. The
link rule is currently a method on `NewSongInput`, so a second model would have to copy it.
Moving it into the type keeps the behaviour of `NewSongInput` the same
(`tests/unit/test_new_song_input.py` keeps passing as written, which is the regression check).

**Alternatives considered**: subclassing `NewSongInput` with every field optional. Rejected:
Pydantic validators keyed on field names do not follow an override that changes the type to
`X | None`, and it would make "edit" inherit "create" semantics, such as the default `""` link.

## R-02 Telling "omitted" apart from "null" and requiring a non-empty body

**Decision**: `SongChangesInput(StrictBaseModel)` declares `title`, `artist` and `youtube_link` as
`<type> | None = None`. A `field_validator(..., mode="before")` rejects an explicit `null` with the
field name in the message. A `model_validator(mode="after")` rejects an empty `model_fields_set`.
The repository applies `model_dump(exclude_unset=True)`, so an omitted field is never written.

**Rationale**: Pydantic does not validate defaults, so the before-validator only runs for keys the
client actually sent: `null` gives a `400` on that field, and an omitted key stays `None` and
untouched (FR-003, spec Assumptions). `extra="forbid"` from `StrictBaseModel` already rejects
`category` and any other key (FR-004). Every failure is a `PydanticValidationError`, which the
handler already maps to `400 VALIDATION_ERROR` with `field_errors`, as for create.

**Alternatives considered**: a DRF serializer with `partial=True`. Rejected: create uses Pydantic,
and two validation stacks for one resource would drift.

## R-03 When the duplicate check runs

**Decision** (spec clarification Q1): the service computes the normalized pair of the stored song
and of the song after the changes, as `(title.strip().lower(), artist.strip().lower())`. Only when
the two differ does it query `song_exists(title, artist, exclude_id=song.id)`. The existing
`song_exists` gets an optional `exclude_id`, so create and edit share one query.

**Rationale**: legacy rows may already repeat a pair, because there is no DB constraint. An edit
that does not change the pair cannot create a duplicate, so checking it would only block fixing a
legacy duplicate's link. `iexact` is the comparison create already uses. Input is trimmed by the
DTO. Stored values are already trimmed: they come from the API (trimmed) or the Django admin, whose
`CharField` form fields strip by default. So `iexact` covers "ignoring case and surrounding
whitespace" without a `Trim()` annotation that create does not have.

**Alternatives considered**: always checking with `exclude_id` (rejected in clarification Q1);
a `Lower(Trim())` DB comparison (rejected because it would make edit stricter than create for the
same pair).

## R-04 Measuring "in use"

**Decision**: a single repository method `get_song_usage(song_id) -> SongUsage`, with two queries:
- `Played.objects.filter(song_id=…).values("date").distinct().count()` gives the distinct play
  dates (clarification Q2).
- `SetlistItem.objects.filter(song_id=…).values_list("setlist__date", flat=True).distinct().order_by("setlist__date")`
  gives the distinct setlist dates, ascending.

**Rationale**: these are exactly the two `PROTECT` relations on `Song`. `SetlistItem` belongs to the
same feature, so no cross-feature import is involved. The cost is constant (two queries), with no
loop. `SongUsage` is a Pydantic DTO (`plays: int`, `setlist_dates: list[date]`, plus an `in_use`
property) rather than a tuple or dict, per CLAUDE.md §7.

**Alternatives considered**: relying only on `ProtectedError.protected_objects`, as
`delete_service_window` does. Rejected as the primary path: it counts rows, not distinct dates,
and it needs a delete attempt first. It is still the fallback for the race (R-05).

## R-05 The race between check and delete

**Decision**: `SongRepositoryImpl.delete_song(song)` runs `song.delete()` inside
`transaction.atomic()` and catches `ProtectedError` **and** `IntegrityError`. On either one it
re-reads `get_song_usage`. If the song is now in use, it raises `SongInUseError` with the fresh
numbers. If not, the original exception is re-raised: it was something else, and hiding it would
bury a real fault.

**Rationale**:
- `ProtectedError`: Django's collector checks `PROTECT` before issuing any `DELETE`. A play
  committed between the service's check and the collector's collect raises it, and nothing has
  been deleted yet.
- `IntegrityError`: on PostgreSQL, Django creates foreign keys `DEFERRABLE INITIALLY DEFERRED`. A
  play committed *after* the collect but before our commit is caught by the database at commit.
  `ATOMIC_REQUESTS` is off, so the repository's own `atomic()` is the outermost block and the
  commit happens on its exit, inside the `try`. The whole cascade (chord charts, lyrics, song)
  rolls back.
- The re-check-then-reraise shape is the existing precedent in
  `gallery_trash_service._restore_batch`.

**Testability**: the `ProtectedError` path is tested for real against SQLite. The test hands the
service a repository subclass whose `get_song_usage` reports "free" while a `Played` row exists,
so the real collector refuses the delete. The deferred-FK `IntegrityError` path cannot be produced
on SQLite in-memory. A unit test drives it through a named fake that raises `IntegrityError` from
the delete.

**Alternatives considered**: `select_for_update` on the song. Rejected: it does not stop a
concurrent `INSERT` into `Played`, which takes only a key-share lock on the parent row.

## R-06 Where the pt-BR message is built

**Decision**: in `SongInUseError.__init__` (`core/domain/exceptions.py`), from
`song_id, title, plays, setlist_dates`. A module-level helper formats the reasons:
- plays: `foi tocada em 1 domingo` / `foi tocada em N domingos`
- setlists: `está na setlist de DD/MM/AAAA` / `está nas setlists de A, B e C`
- both reasons joined with ` e `, prefixed by `A música "<title>" não pode ser excluída: ` and
  ended with `.`

`extra_context()` returns `{"song_id", "title", "plays", "setlist_dates": [ISO strings]}`.

**Rationale**: `ServiceInUseError` and `DuplicateSongError` build their own messages. Keeping the
wording in the exception keeps `SongService` short. The exception module already imports `date`.
The pt-BR text is user-facing content, which CLAUDE.md §1 allows in Portuguese. The divergence from
the English precedent is recorded in the spec's Assumptions.

## R-07 Not found

**Decision**: a new `SongNotFoundError(NotFoundError)` with `song_id` and
`extra_context() == {"song_id": …}`, following `ChordChartNotFoundError`. `SongsNotFoundError`
(batch, `missing_song_ids`) is untouched.

## R-08 Cached reads after edit/delete (FR-018)

**Finding**: `core.http.utils._not_modified_or_response` derives the ETag as a SHA-256 of the
response body. Per endpoint:

| Read | ETag? | Embeds song data? | Effect of edit/delete |
|------|-------|-------------------|-----------------------|
| `GET api/songs/` | yes, body-derived | yes | new body, new ETag |
| `GET api/songs-by-sunday/` | yes, body-derived | `song`, `artist` | new body, new ETag |
| `GET api/top-songs/` | yes, body-derived | `song__title` | new body, new ETag |
| `GET api/suggested-songs/` | **no** (plain `Response`) | yes | nothing cached, always fresh |
| `GET api/top-tones/` | yes | no | unaffected |

No code change is needed. One integration test proves the first three, by sending the old ETag
after an edit and expecting `200`.

## R-09 Permission and classification

**Decision**: `SongDetailAPI.permission_classes = [IsAuthenticated, scope_permission(Scope.SONGS)]`
with no overrides, the same declaration as `ChordChartDetailAPI`. The default mapping
(`core/domain/access.py`) gives `PATCH` `manage` and `DELETE` `owner`. Both rows are added to the
`songs` table of `specs/012-feature-role-permissions/spec.md` (Endpoint Classification, `default`)
and to `ENDPOINTS` in `core/tests/integration/test_management_access_matrix.py` (FR-017). That
test already covers 401, 403 below the level, Leader 403 on every `DELETE`, and Admin reaching
every row.

The permission is class-level, so an unknown id yields `403` for an under-privileged caller and
`404` only past the check. This is what the matrix test expects.

## R-10 DI

No new provider. `SongService` and `SongRepositoryImpl` are already registered in `config/di.py`,
and `features.songs.views.songs` is already wired. The new view lives in that module.
