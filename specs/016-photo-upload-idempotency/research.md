# Research: Idempotent Photo Upload

Decisions taken while planning `specs/016-photo-upload-idempotency/spec.md`, grounded in the code
as of commit `7603253` (end of feature 015).

## R-01 Where the id is stored and how uniqueness is enforced

**Decision**: `Photo.client_upload_id = CharField(max_length=64, null=True, blank=True,
editable=False)` and a named `UniqueConstraint(fields=["client_upload_id"],
name="unique_photo_client_upload_id")` in `Photo.Meta.constraints`. No condition.

**Rationale**: SQL `NULL`s are distinct in both PostgreSQL (production) and SQLite (tests), so
photos without an id never collide and a plain constraint already means "unique when set". The
constraint covers every row, trashed included (spec FR-006): if a trashed row released its id, a
retry would create a second photo while the first can still be restored. `editable=False` keeps
the field out of every ModelForm, `PhotoAdmin` included (it declares no `fields`, so Django
builds the form from the editable fields). The unique constraint creates its own index, which
serves the lookup of R-03. `max_length=64` matches the validation rule (R-05).

**Alternatives considered**:
- Conditional constraint (`condition=Q(client_upload_id__isnull=False)`): same behaviour, a
  slightly smaller index; rejected as unnecessary noise given how NULL works.
- Separate `PhotoUpload` table (id → photo): would let the purge keep the id after the row is
  gone, but spec FR-011 wants a purged id to be free, and it adds a join and a model for nothing.
- `unique=True` on the field: equivalent; the named `Meta` constraint follows the style of
  `Album` and gives a stable name to recognise in R-04.

## R-02 Order of checks in the request

**Decision**:

1. Permission (`GALLERY_WRITE`, unchanged).
2. View: `album_id` present and integer (`require_int`), at least one file (existing `400`),
   `client_upload_id` sent at most once (new helper `optional_single_value` in
   `core/http/parsing.py`, `400` naming the field and the count).
3. Service, when an id is present: id format and exactly one file
   (`features/gallery/domain/upload_rules.py`, pure), then the lookup of R-03 **before**
   `_require_album`.
4. No id, or no row carries it: the 013 path, unchanged (`_require_album`, per-file validation,
   store).

**Rationale**: FR-005 puts every shape check before any lookup or storage. FR-012 forbids looking
up the album on a repeat, so the id lookup must come before `_require_album`: an unknown or
trashed `album_id` then only matters for a first upload. The repeated-field check reads the raw
multipart list, which only the view sees; the format and file-count rules are domain rules
(one id names one photo) and are unit-tested without HTTP.

**Alternatives considered**: all checks in the view — rejected: the file-count rule is business,
and the service would trust callers other than the view (the admin page passes no id, but a
future caller could).

## R-03 The fast path: lookup before any work

**Decision**: `GalleryRepository.find_client_upload(client_upload_id) -> ClientUploadMatch | None`,
reading `Photo.all_objects` (live and trashed) and returning `photo_id` and `trashed`
(`deleted_at is not None`). The service then:

- live → `get_photo(photo_id)` and `UploadResult(accepted=[view])`, log
  `gallery_upload_deduplicated`;
- trashed → log `gallery_upload_original_trashed`, raise `UploadedPhotoTrashedError` (R-06);
- `None` → first upload.

**Rationale**: a plain retry (the common case: the first request finished long ago) skips the
pixel check, the thumbnail and every write. `all_objects` is required to see a trashed original;
the gallery spec lists who may use it (trash, restore, purge, media lookup), and the upload
deduplication joins that list (spec adjustment, plan). A photo trashed with its album is itself
trashed (spec 014 cascades the batch), so `deleted_at` on the photo row is the whole answer.

**Alternatives considered**: `get_or_create` — rejected: it would have to run after the files are
written (the row needs their names), so it saves nothing on a plain retry and still needs R-04 for
the race.

## R-04 The race: the constraint decides

**Decision**: `create_photo` runs its insert inside its existing `transaction.atomic()`; an
`IntegrityError` is caught there and, when a row now carries the same `client_upload_id`, turned
into the internal domain exception `ClientUploadIdTakenError(client_upload_id)`; any other
`IntegrityError` is re-raised. `_persist` already deletes the files it wrote on any exception, so
the service only catches `ClientUploadIdTakenError` after it, re-runs the R-03 lookup and answers
as a repeat (live or trashed).

**Rationale**: FR-014 wants the database to decide. Two requests that both miss the fast path
both write their files and then insert; the second insert waits on the unique index until the
first commits (PostgreSQL, READ COMMITTED) and then fails. Nothing else of the loser survives:
the position was taken inside the rolled-back atomic block, and the automatic cover is set only
after a successful `_persist` (`GalleryService._store_one`), so FR-015 holds without new code.
The repository keeps `IntegrityError` (a Django type) out of the service, as the architecture
requires; checking for the row instead of parsing the constraint name from the driver message
works on both backends.

**Alternatives considered**:
- `select_for_update` on a lookup row: there is no row to lock before the insert; locking the
  album does not help when the two requests name different albums (FR-012).
- A PostgreSQL advisory lock on a hash of the id: correct, but PostgreSQL-only (tests run on
  SQLite) and a second mechanism beside the constraint the spec already requires.

## R-05 Validating the id

**Decision**: pure function `ensure_valid_client_upload(client_upload_id: str, file_count: int)`
in `features/gallery/domain/upload_rules.py`, with `CLIENT_UPLOAD_ID_MAX_LENGTH = 64` and the
pattern `[A-Za-z0-9_-]`. Raises `InvalidClientUploadIdError` (`400`, extra fields
`client_upload_id` truncated to the limit, `expected`) for empty, too long or a bad character —
the message names the length or the first offending character — and
`ClientUploadNeedsOneFileError` (`400`, `file_count`) otherwise. Messages in English: only a
client bug reaches them (as `OrderMismatchError`, `core/http/parsing.py`).

**Rationale**: FR-002 to FR-004 and CLAUDE.md §8 (the message carries the offending value and
the expected shape). `re.fullmatch` on an ASCII class, not `str.isalnum`, which accepts non-ASCII
letters. The echoed value is truncated so a 10 MB field cannot be reflected back.

**Alternatives considered**: require a UUID (`uuid.UUID(value)`) — rejected: the spec keeps the
id opaque; the app uses a UUID v4, but the server must not depend on it.

## R-06 The trashed-original refusal

**Decision**: `UploadedPhotoTrashedError(ConflictError)` in `core/domain/gallery_exceptions.py`
(re-exported from `core/domain/exceptions.py`), detail in Portuguese — "Esta foto já foi enviada
e depois apagada; ela está na lixeira." — and `extra_context` `{"client_upload_id": ...}` only.

**Rationale**: `409` `CONFLICT` through the existing mapping (`core/http/exceptions.py`); no new
error code (spec clarification Q1). No photo id in the body (FR-010), as spec 015 keeps trash
contents from callers with `manage`. Portuguese because the app shows it to the user.

## R-07 Logging

**Decision**: `logger = logging.getLogger("features.gallery")` (already in the gallery services),
`logger.info("gallery_upload_deduplicated", extra={"photo_id", "actor_id"})` and
`logger.info("gallery_upload_original_trashed", extra={"photo_id", "actor_id"})`, `actor_id` as
`str(uploader_id)` (or `None`). Emitted by `GalleryService` for both the fast path and the race
loser.

**Rationale**: spec 002 JSON format through `extra`, as `gallery_tags_changed` and the purge lines
do; ids only (FR-019). The trashed-original line carries the photo id: logs are not a response,
and support needs to find the row.

## R-08 Where the new code lives

**Decision**: `GalleryService` (232 lines) gains `client_upload_id: str | None = None` on
`upload_photos` and three private helpers (`_existing_upload`, `_answer_existing`,
`_store_first`) — about 45 lines, still under 300. The rules go to a new
`domain/upload_rules.py` rather than `gallery_rules.py` (names), one responsibility per module.
`NewPhoto` gains `client_upload_id: str | None = None`; new DTO `ClientUploadMatch` in
`gallery_dtos.py`. The admin upload page does not change: it calls `upload_photos` without the
argument (FR-016).

**Alternatives considered**: a separate `PhotoUploadService` — rejected: the dedup is a branch of
the one upload use case, and splitting would duplicate `_require_album` / `_store_one` wiring.

## R-09 Migration

**Decision**: generated `gallery/0006_photo_client_upload_id.py` (`AddField` + `AddConstraint`).
No data migration: existing photos keep `NULL`.

**Rationale**: a nullable column with no default is a metadata-only change in PostgreSQL; the
unique index is built over a few thousand rows. Not a model move or rename, so CLAUDE.md §5's
compensating controls are not required; the forward/backward run on a restored production dump
is still in the quickstart because it costs little.

## R-10 Testing the race without PostgreSQL

**Decision**:
- Unit (fakes): `FakeGalleryRepository` gains an in-memory id index and a switch
  `take_client_upload_on_create` that makes `create_photo` raise `ClientUploadIdTakenError` after
  inserting a competing photo, as a concurrent winner would; the test checks that the fake
  storage holds no file of the loser and the answer carries the winner.
- Integration (SQLite): `create_photo` with an id already stored raises
  `ClientUploadIdTakenError`, and a `NewPhoto` violating nothing else still inserts.
- Manual, PostgreSQL: two uploads with the same id fired in parallel against the dev stack
  (quickstart §3).

**Rationale**: tests run on SQLite, which serialises writers and cannot reproduce the
PostgreSQL wait-on-unique-index; the logic that matters (translate the violation, clean up,
answer as a repeat) is exercised deterministically by the fake and the integration test, and the
real race once by hand.
