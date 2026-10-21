# Research: Church Events

Decisions taken while planning `specs/020-church-events/spec.md`. Contract decisions agreed with
the app session are in the spec's Clarifications and are not repeated here.

The requester asked for plan, tasks and implementation to run unattended (2026-10-21). Decisions
marked **(unattended)** were taken without them and are listed in the completion report so they
can be revisited.

## R-01 — Where the image processor lives **(unattended)**

**Decision**: move `features/gallery/imaging/` (the `ImageProcessor` protocol and
`PillowImageProcessor`) to `core/files/imaging/`, unchanged except for two new methods
(`upright_dimensions`, `fitted_jpeg`). Gallery imports are updated; behaviour does not change.

**Rationale**: the constitution forbids features importing each other, and CLAUDE.md §8 forbids
duplication. Events need the same decode / EXIF-orient / flatten-alpha / JPEG-encode pipeline the
gallery already owns. `core/files/` already holds the shared upload validation, so the processor
belongs next to it.

**Alternatives**: a second Pillow wrapper in `features/events` (duplicates `_flatten`,
`_to_jpeg` and the decode-error mapping); importing from `features.gallery` (constitution
violation).

## R-02 — Fitting the image to 1920 × 1080

**Decision**: new `ImageProcessor.fitted_jpeg(source, max_width, max_height, quality)`: Pillow
`thumbnail((max_width, max_height))` after the same `_flatten` step — keeps aspect, never
upscales. Quality 85, the gallery's derivative quality, as an events constant.

**Rationale**: `bounded_jpeg(longest_side=1920)` lets a ratio at the +2% edge
(1920 × 1102) exceed 1080 in height. The spec bounds both sides.

## R-03 — Measuring the ratio after EXIF orientation

**Decision**: new `ImageProcessor.upright_dimensions(source)`: header size, swapped when the EXIF
orientation tag is 5–8 (a 90° rotation). No pixel decode.

**Rationale**: the spec measures the image as displayed. `dimensions()` returns the stored
pixel size, which is wrong for a phone photo tagged "rotate 90°".

## R-04 — Image validation order and limits

**Decision**: `detect_image_extension` (core: size ≤ 10 MB, decoded format) → reject `gif`
(core allows it, events do not) → `upright_dimensions` → pixel limit (50 MP, events constant,
`ImageTooLargeError`) → minimum 640 × 360 → ratio within ±2% of 16/9 → `fitted_jpeg`. Every
failure becomes `EventImageInvalidError` (400, `field_errors.image`), message in Portuguese with
the received value and the expected shape.

Ratio check: `abs(width / height - 16 / 9) <= 16 / 9 * 0.02`.

**Rationale**: cheap checks first; nothing is decoded in full before size, format and pixel
count pass. Limits are module constants in `features/events/domain/event_image_rules.py`.

## R-05 — Anonymous access to `events/` media **(unattended detail)**

**Decision**:

- `MediaFileAPIView` replaces `IsAuthenticated` with `IsAuthenticatedOrEventImage`: allows an
  authenticated caller, or any caller when the requested path's first segment is `events`.
  Authentication still runs first, so an invalid token is `401` on every path (FR-020).
- `FOLDER_RULES["events"] = MediaAudience.EVENT_VISIBILITY`. For that audience the service asks a
  new port, `EventImageLookup.is_public_event_image(path) -> bool | None` (True public, False
  members-only, None no event). `None`, or `False` for a non-member, raises
  `MediaFileNotFoundError` → `404`, logged as `not_found`. The lookup runs after path validation
  and before the existence check.
- The port is declared in `features/media/repositories/interfaces.py`, implemented in
  `features/events/repositories/event_image_lookup.py`, wired in `config/di.py` — the same
  pattern as `TrashedMediaLookup` (spec 014 R-05).
- The viewer of an anonymous request: `is_member=False`, `can_view_members=False`,
  `own_profile_folder=None` (no username to compute it from).

**Rationale**: smallest change that keeps every other folder's `401` for anonymous callers and
default deny. Bool-or-None keeps the media feature from knowing the events vocabulary.

**Alternatives**: a separate public media route (two code paths for path validation — rejected,
009 relies on one); making `events/` member-only (breaks visitors, rejected by the app).

## R-06 — Public endpoints and authentication

**Decision**: `permission_classes = [AllowAny]` with the default authentication classes. DRF's
`JWTAuthentication` raises on a malformed or expired token → `401 AUTHENTICATION_FAILED`; no
header → anonymous. Membership is `IsMemberUser().has_permission(...)`, the same check the media
view uses. Responses are `private` (body depends on the caller): `_not_modified_or_response(...,
private=True)`.

## R-07 — "Today" and the active window

**Decision**: `features/events/domain/event_dates.py` holds `EVENTS_TIME_ZONE =
ZoneInfo("America/Sao_Paulo")`, `today_in_events_zone(now)`, `last_day(start, end)`. The service
gets `now` from the injected `Clock` and passes `today` to the repository, which filters
`end_date >= today OR (end_date IS NULL AND start_date >= today)` (active) or its negation
(past). Spelled as two branches rather than `Coalesce` so each can use its column and the
typed ORM stubs follow the field names.

**Rationale**: explicit zone, independent of `settings.TIME_ZONE`; clock injected so tests pin
midnight edges (the gallery and setlists already inject `Clock`).

## R-08 — Ordering with absent times

**Decision**: ORM `F("start_time").asc(nulls_first=True)` for the public list and
`.desc(nulls_last=True)` for management, then id. Supported on PostgreSQL (prod) and SQLite
(tests).

## R-09 — Storage, paths and replacement

**Decision**: `DefaultStorageEventImageStorage` saves `events/{uuid4}.jpg` on default storage;
`Event.image_path` is a `CharField(max_length=255, unique=True)` holding that name (unique ⇒
indexed, serves the media lookup). Create: save file → insert row; on any failure delete the new
file. Edit with image: save new file → update row → delete old file; on failure delete the new
file and keep the old. Delete: delete row → delete file. A file already gone is not an error.

**Rationale**: a plain path column (not `ImageField`) keeps Django from touching the file and
keeps storage behind the project's own interface, as the gallery does.

## R-10 — Partial edit and nulls

**Decision**: the PATCH serializer validates only sent keys (`partial=True`); the DTO's
`model_fields_set` tells "leave alone" from "clear". Multipart `""` on a nullable date/time field
becomes `None` (DRF `allow_null` on HTML input). `location`/`description` are stripped; empty
becomes `None` (DTO validator). The date rule is checked by the service on the merged event
(FR-004) and raised as `EventDatesInvalidError` with `field_errors.end_date`.

## R-11 — Permissions migration

**Decision**: data migration `core/0008_events_owner_for_leader_media.py`, a copy of 0006's
shape (`events__manage` → `events__owner` for groups `leader`, `media`; reverse swaps back;
permission rows get-or-created). Reason at the top of the file (CLAUDE.md §5).

## R-12 — Domain exceptions module

**Decision**: new `core/domain/event_exceptions.py` (`EventNotFoundError`,
`EventImageInvalidError`, `EventDatesInvalidError`, `EventStatusFilterError`), re-exported from
`core/domain/exceptions.py` like the gallery and setlist modules (that file is near the 500-line
limit). Validation exceptions carry `field_errors` through `extra_context()`.

## R-13 — Django admin **(unattended)**

**Decision**: no Django admin for events. Everything is done from the app; an admin form would be
a second write path that bypasses image validation and processing.
