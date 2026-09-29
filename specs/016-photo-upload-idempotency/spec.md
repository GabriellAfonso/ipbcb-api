# Feature Specification: Idempotent Photo Upload

**Feature Branch**: `016-photo-upload-idempotency`

**Created**: 2026-09-29

**Status**: Draft

**Input**: User description: "Add an optional client upload id to POST /api/photos/, so the
Android app can retry an upload safely without creating duplicate photos." (full request —
current state, what to build, out-of-scope list and five open decisions — in the
`/speckit-specify` invocation that created this spec.)

## Context

The app uploads photos one per request, in sequence, from a background queue that retries on a
network failure or a `5xx`. When the server stores the photo but the answer never reaches the
phone (timeout, connection dropped on mobile data), the queue retries and the server stores the
same photo a second time. Nothing in the request today lets the server tell a retry from a new
upload.

This feature adds an optional **client upload id** to `POST /api/photos/`: the app generates it
once per photo and repeats it on every retry, and the server answers a repeat with the photo it
already has instead of storing another.

### Relation to other specs

- **`specs/gallery/spec.md`** — the domain spec; `Photo` gains the stored id and
  `POST /api/photos/` gains the field, its rules and its errors (FR-020).
- **`specs/013-gallery-write-api/contracts/gallery-api.md`** — the upload contract gains the
  field, the deduplicated answer and the new `400`s (FR-020).
- **`specs/014-gallery-trash-sync/`** — the trash and the purge are unchanged; this spec only
  decides what a repeated id means once its photo is trashed or purged (FR-010, FR-011).
- **`specs/002-structured-json-logging/`** — a deduplicated upload is logged in its format.
- **`specs/001-api-error-handling/`** — every refusal uses its canonical error shape.

## Clarifications

### Session 2026-09-29

- Q: A repeated id whose original is in the trash? → A: refuse with `409` `CONFLICT` and a
  Portuguese detail the app shows; the queue drops the item on a 4xx (FR-010).
- Q: A repeated id with a different `album_id` than the original's current album? → A: return
  the original as it is; the id identifies the upload, not its destination, and `album_id` is
  not looked up on a repeat (FR-012).
- Q: Status of a deduplicated answer? → A: `201`, the same as the first time (FR-013).
- Q (planning): Can a repeat skip reading the file? → A: no: the multipart body is received
  before the endpoint runs; what a repeat skips is examining it — validation, pixel check,
  thumbnail, EXIF — and every write (FR-009).
- Q (planning): Who may read trashed rows? → A: the upload deduplication lookup joins the trash,
  restore, purge and media-lookup code in the gallery spec's list of `all_objects` users, since it
  must see a trashed original (FR-010, FR-020).

## Definitions

### Client upload id

An opaque string the app generates once per photo it queues (a UUID v4 in practice) and sends,
unchanged, on the first request and on every retry of that photo. The server never interprets
it: it only stores it on the photo created by the first request and compares later requests
against it, character for character.

### Repeated upload

A request whose client upload id is already stored on a photo row. The photo created by the
first request is the **original**.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A retried upload does not duplicate the photo (Priority: P1)

A manager uploads a photo from the app on mobile data. The server stores it, but the connection
drops before the answer arrives. The app's queue retries with the same client upload id. The
server recognizes the retry, stores nothing, and answers with the photo it already has; the app
marks the item done. The album shows the photo once.

**Why this priority**: it is the whole point of the feature — duplicates today appear exactly in
the conditions the app is used in (phones on mobile data at church events).

**Independent Test**: send the same upload twice with the same id and check that one photo
exists and both answers carry it.

**Acceptance Scenarios**:

1. **Given** no photo carries id `X`, **When** the app uploads a photo with id `X`, **Then** the
   answer and everything stored are exactly as for an upload without an id, and the new photo
   carries `X`.
2. **Given** a live photo carries id `X`, **When** the app uploads again with id `X`, **Then** no
   photo, file or thumbnail is created, the album's photos, positions and cover are unchanged,
   and the answer is a success whose `accepted` holds the original's Photo resource as it is now
   and whose `rejected` is empty.
3. **Given** a live photo carries id `X`, **When** the repeat carries a file that is different,
   invalid or too large, **Then** the answer is still the original photo — the file of a repeat is
   never examined.
4. **Given** a live photo carries id `X`, **When** the answer to the repeat is read, **Then** the
   Photo resource has no field exposing the id.
5. **Given** a live photo carrying id `X` was moved to album B after being uploaded into A,
   **When** the app retries into A, **Then** the answer is `201` with the photo in album B.
6. **Given** the photo carrying id `X` was deleted (in the trash), **When** the app retries with
   `X`, **Then** the answer is `409` `CONFLICT` with a Portuguese detail saying the photo was
   deleted, nothing is stored, and the photo stays in the trash.

---

### User Story 2 - Two simultaneous retries still make one photo (Priority: P1)

The queue fires a retry while the first request is still being processed (it timed out on the
phone but not on the server). Both requests carry the same id. Exactly one photo is created; the
request that did not create it answers with the one that was.

**Why this priority**: the timeout that causes the retry is often the same slow request still
running, so the two overlap in practice; a check made only before storing would let both pass.

**Independent Test**: run two uploads with the same id concurrently and check that one photo
exists, both answers are successes carrying it, and no orphan file is left on disk.

**Acceptance Scenarios**:

1. **Given** two requests with id `X` in flight at once, **When** both finish, **Then** exactly
   one photo carries `X` and both answers hold that photo in `accepted`.
2. **Given** the request that lost the race had already written files, **When** it gives way,
   **Then** those files are removed and nothing else it did remains (no position taken, no cover
   set).

---

### User Story 3 - Uploads without an id behave as today (Priority: P1)

Tooling and the Django admin upload page send no id. Their requests, including multi-file ones,
behave exactly as before this feature.

**Why this priority**: the id is optional by design; breaking the existing callers is not
acceptable.

**Independent Test**: the existing upload tests pass unchanged; an upload without an id twice
creates two photos, as today.

**Acceptance Scenarios**:

1. **Given** a request without the field, **When** it is sent with one or several files,
   **Then** statuses, bodies and stored data are those of feature 013.
2. **Given** a photo uploaded without an id, **When** another upload arrives, with or without an
   id, **Then** that photo never matches it.

---

### User Story 4 - A malformed id is refused clearly (Priority: P2)

A client sends an id that is empty, too long, made of characters outside the allowed set, or
sends an id with several files. The server refuses the request before storing anything, with a
`400` that names the field and says what shape was expected.

**Why this priority**: protects the uniqueness guarantee and gives client developers an
immediate, readable error; it matters only to a misbehaving client.

**Independent Test**: send each malformed variant and check the `400`, its message, and that
nothing was stored.

**Acceptance Scenarios**:

1. **Given** an id with more than 64 characters, or with a character other than an ASCII letter,
   digit, `-` or `_`, or an empty value, **When** it is sent, **Then** the answer is `400`
   `VALIDATION_ERROR` naming `client_upload_id`, the received length or the first offending
   character, and the expected shape; nothing is stored.
2. **Given** an id and two or more files, **When** the request is sent, **Then** the answer is
   `400` `VALIDATION_ERROR` naming `client_upload_id` and the number of files received; nothing is
   stored.
3. **Given** the field sent more than once in the same request, **When** it is read, **Then** the
   answer is `400` `VALIDATION_ERROR` naming the field.

---

### User Story 5 - A deduplicated upload is visible in the logs (Priority: P3)

When a repeat is answered with an existing photo, the server logs one structured line saying
so, with the photo id and the actor id, so a spike of retries from the field can be seen.

**Why this priority**: observability only; the behaviour does not depend on it.

**Independent Test**: repeat an upload and check the single log line and its fields.

**Acceptance Scenarios**:

1. **Given** a repeated upload, **When** it is answered, **Then** one line `gallery_upload_deduplicated`
   is logged with `photo_id` and `actor_id` — ids only, no names and no file name.
2. **Given** a first upload with an id, **When** it is answered, **Then** no deduplication line
   is logged.

### Edge Cases

- **Original in the trash**: `409` `CONFLICT`, nothing stored (FR-010).
- **Original purged**: the row is gone and its id with it; the request is a new upload (FR-011).
- **Original restored from the trash**: live again; a repeat is answered with it (FR-009).
- **Repeat with a different `album_id`** (the original was moved, or the app changed the target):
  the original is returned as it is, in its current album (FR-012).
- **Repeat whose `album_id` is now unknown or trashed** while the original is live elsewhere:
  the original is returned; `album_id` is not looked up on a repeat, so no `404` (FR-012).
- **Repeat whose original lives under a trashed album**: the original counts as trashed
  (as everywhere outside the trash, spec 014), so `409` (FR-010).
- **Repeat without `album_id` or without a file**: the request is malformed and gets the
  existing `400` of feature 013, before any lookup — a retry always resends the full request.
- **Repeat by a different user**: the id is global (FR-006), so the original is returned; the
  caller holds `manage` on `gallery` and could see the photo anyway.
- **Caller without `manage`**: `403` before the id is looked at, as today.
- **Same id, different letter case**: different ids; comparison is exact.
- **First request's only file rejected** (invalid image): no photo is created, so the id is not
  stored; a retry with the same id is a new upload and is rejected again the same way.
- **Photo edited after upload** (renamed, re-described, tagged): the repeat returns its current
  resource, not the one returned the first time.

## Requirements *(mandatory)*

### Functional Requirements

**The field**

- **FR-001**: `POST /api/photos/` MUST accept an optional multipart field `client_upload_id`.
- **FR-002**: When present, the value MUST be 1 to 64 characters, each an ASCII letter, digit,
  `-` or `_`; otherwise `400` `VALIDATION_ERROR` naming the field, what was received (length or
  first offending character) and the expected shape. A UUID v4 in its canonical form satisfies
  it.
- **FR-003**: When present, the request MUST carry exactly one file in `image`; otherwise `400`
  `VALIDATION_ERROR` naming the field and the number of files received.
- **FR-004**: The field sent more than once MUST be `400` `VALIDATION_ERROR` naming it.
- **FR-005**: The checks of FR-002 to FR-004 MUST run after the permission check and together
  with the existing request checks (`album_id`, file present), before any lookup or storage.

**Storage**

- **FR-006**: A photo MUST store the client upload id it was created with, or none. Among all
  photo rows — live and trashed — a stored id MUST be unique; photos without one are
  unconstrained. [Default taken for open decision 4: global, not per uploader.]
- **FR-007**: The id MUST NOT appear in the Photo resource, in any list, in the change feed, in
  the trash listing, or in the Django admin forms. It MAY be shown read-only on the admin photo
  page.
- **FR-008**: The id MUST be kept for the life of the row; nothing clears it. [Default taken for
  open decision 5.]

**Deduplication**

- **FR-009**: A request whose id is stored on a live photo MUST store and process nothing — the
  file is received but never examined: no validation of it, no thumbnail, no position, no cover, no `updated_at`
  change — and MUST answer with the success body `{"accepted": [<the photo's current
  resource>], "rejected": []}` and the status of FR-013.
- **FR-010**: A request whose id is stored on a trashed photo MUST store and process nothing and
  MUST answer `409` `CONFLICT` with the canonical body, a Portuguese `detail` the app can show
  as is (the photo was uploaded and then deleted; it is in the trash) and `client_upload_id`
  echoing the id. The body MUST NOT carry the photo's id or resource, so a caller with `manage`
  learns nothing else about the trash (as in spec 015, FR-015).
- **FR-011**: A request whose id is stored on no row (never used, or its photo purged) MUST be
  handled as a first upload.
- **FR-012**: A repeated request MUST be answered by FR-009 or FR-010 whatever its `album_id`:
  the id identifies the upload, not its destination. On a repeat `album_id` MUST only be checked
  for presence and integer form (FR-005), never looked up, so an unknown or trashed `album_id`
  does not turn a repeat into a `404`. The original is returned in its current album.
- **FR-013**: A deduplicated answer MUST have status `201`, the same as the first upload.
- **FR-014**: Of any number of concurrent requests with the same id, exactly one MUST create a
  photo. The database's uniqueness on the stored id MUST be what decides, not a lookup made
  before storing; a lookup MAY precede it only to skip work on a plain retry.
- **FR-015**: A request that loses the race MUST leave nothing behind — its stored files removed,
  no position or cover change — and MUST answer as a repeat of the winner (FR-009 to FR-013).

**Unchanged behaviour**

- **FR-016**: A request without the field MUST behave exactly as specified by feature 013,
  including multi-file requests and the Django admin upload page, which never sends an id.
- **FR-017**: A first request with an id MUST answer and store exactly what the same request
  without an id would, plus the stored id.
- **FR-018**: The change feed, the trash, the purge, tags and every other write endpoint MUST
  NOT change.

**Observability**

- **FR-019**: A deduplicated answer (FR-009) MUST log one line `gallery_upload_deduplicated` in the spec 002 format with `photo_id` and
  `actor_id`. A request that lost the race (FR-015) logs the same line. A refusal for a
  trashed original (FR-010) logs one line `gallery_upload_original_trashed` with `photo_id` and
  `actor_id`. A first upload logs nothing new.

**Specs**

- **FR-020**: `specs/gallery/spec.md` and `specs/013-gallery-write-api/contracts/gallery-api.md`
  MUST gain the field, the stored id, the deduplication rules and the new errors, in the same
  commit as the code.

### Key Entities

- **Photo** *(existing)*: gains an optional, write-once client upload id, unique among all photo
  rows when set, never exposed in the resource.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Repeating an upload with the same id any number of times — sequentially or up to
  10 at once — leaves exactly one photo in the album and every answer is a success carrying it.
- **SC-002**: A repeated upload leaves no new file on disk and no change to any existing photo or
  album, verified by comparing their state before and after.
- **SC-003**: 100 % of the existing upload tests pass unchanged.
- **SC-004**: Every malformed-id request is refused with a message that names the field and the
  expected shape, and stores nothing.
- **SC-005**: A repeated upload answers at least as fast as the first upload of the same file,
  since no file is processed.
- **SC-006**: Every deduplicated answer produces exactly one log line with the photo id and the
  actor id.

## Assumptions

- The app generates a fresh UUID v4 per photo and never reuses one for a different photo; a
  collision between two different photos is treated as impossible.
- A retry resends the whole request (same `album_id`, same file, same id); the server does not
  rely on this beyond the id.
- The 64-character limit and the character set leave room for formats other than a UUID without
  allowing whitespace or separators that could hide a mismatch.
- Uniqueness is global (open decision 4): a UUID v4 makes a per-uploader scope unnecessary, and a
  global scope means a retry answered after the uploader's account changed still matches.
- The id is kept for the life of the row (open decision 5): it costs one short column, and
  clearing it would reopen the duplicate window for a retry that arrives late.
- Existing photos get no id; the column is added empty.
- Permission is unchanged: `manage` on scope `gallery`.

## Out of Scope

- Any change to the change feed, trash, tags or the other write endpoints.
- Deduplicating by file content (hash) or by filename.
- Idempotency for any endpoint other than `POST /api/photos/`.
- Any Android app change.
