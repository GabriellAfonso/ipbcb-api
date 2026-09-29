---

description: "Task list for feature 016 — idempotent photo upload"
---

# Tasks: Idempotent Photo Upload

**Input**: Design documents from `specs/016-photo-upload-idempotency/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/photo-upload-api.md,
quickstart.md

**Tests**: included — CLAUDE.md §10 requires a test for every new function, with named fakes.

**Organization**: tasks grouped by user story; paths relative to the repository root. Commands
run from `server/` with `.venv_windows`. Every commit must leave the whole tree type-correct
(whole-tree mypy hook), so a task that changes a Protocol also updates its fake.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on an unfinished task)
- **[Story]**: US1–US5 from spec.md

---

## Phase 1: Setup (Specs)

**Purpose**: spec before code, in the same commit as the first code step (CLAUDE.md §6.2, plan
step 0).

- [X] T001 Update `specs/gallery/spec.md`: Photo table gains `client_upload_id` (CharField 64,
  null, unique among all rows when set, never serialized); the `all_objects` note gains "the
  upload deduplication lookup"; `POST /api/photos/` section gains the field, the rules (1–64 of
  `A-Z a-z 0-9 - _`, once, exactly one file), the outcomes (live original → `201` current
  resource, nothing stored, `album_id` not looked up; trashed → `409` `CONFLICT`; purged → new
  upload) and the race rule; Errors table gains the three `400`s and the `409`; a line on the two
  log events `gallery_upload_deduplicated` / `gallery_upload_original_trashed`
- [X] T002 [P] Add a "`client_upload_id`" subsection under `POST /api/photos/` in
  `specs/013-gallery-write-api/contracts/gallery-api.md`, copied from
  `specs/016-photo-upload-idempotency/contracts/photo-upload-api.md` (field, outcomes table,
  bodies, logs)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: exceptions, rules, schema, DTOs and repository every story uses.

**⚠️ CRITICAL**: no user story work until this phase is complete.

- [X] T003 [P] Add to `server/core/domain/gallery_exceptions.py`, each with docstring + example
  and `extra_context`: `InvalidClientUploadIdError(ValidationError)` (`client_upload_id` cut to
  64 chars, `expected`; message names the length or the first offending character and position,
  English), `ClientUploadNeedsOneFileError(ValidationError)` (`file_count`; message
  "Field 'client_upload_id' identifies one photo; send exactly one file in 'image', got N."),
  `UploadedPhotoTrashedError(ConflictError)` (`client_upload_id`; detail
  "Esta foto já foi enviada e depois apagada; ela está na lixeira."),
  `ClientUploadIdTakenError(ConflictError)` (`client_upload_id`; internal, docstring says it never
  reaches HTTP). Re-export all four from `server/core/domain/exceptions.py` like the other gallery
  exceptions
- [X] T004 [P] Unit tests for T003 in `server/core/tests/unit/test_gallery_exceptions.py`: error
  codes (`VALIDATION_ERROR`, `CONFLICT`), `extra_context` keys, truncation to 64, messages carry
  the offending value; `UploadedPhotoTrashedError` body has no photo id
- [X] T005 [P] Create `server/features/gallery/domain/upload_rules.py`:
  `CLIENT_UPLOAD_ID_MAX_LENGTH = 64`, the ASCII pattern, and
  `ensure_valid_client_upload(client_upload_id: str, file_count: int) -> None` raising
  `InvalidClientUploadIdError` (empty, too long, bad character) then
  `ClientUploadNeedsOneFileError` (`file_count != 1`); pure, no Django import
- [X] T006 [P] Unit tests in `server/features/gallery/tests/unit/test_upload_rules.py`: canonical
  UUID v4 passes; 64 chars passes; 65 fails with length in message; empty fails; space, `é`,
  `/`, `.` fail naming the character and position; 0 and 2 files fail with `file_count`
- [X] T007 [P] Add `optional_single_value(values: Sequence[Any], field: str) -> str | None` to
  `server/core/http/parsing.py` (none → `None`; one → `str(value)`; more → `ValidationError`
  "Field 'X' must be sent at most once, got N values."), docstring with example
- [X] T008 [P] Unit tests for T007 in `server/core/tests/unit/test_parsing_guards.py`: empty list,
  one value, two values (message names field and count)
- [X] T009 Add `client_upload_id = models.CharField(max_length=64, null=True, blank=True,
  editable=False)` to `Photo` in `server/features/gallery/models/gallery.py`, with a comment
  citing specs/016 R-01, and `models.UniqueConstraint(fields=["client_upload_id"],
  name="unique_photo_client_upload_id")` in `Photo.Meta.constraints`
- [X] T010 Run `python manage.py makemigrations gallery --name photo_client_upload_id` to generate
  `server/features/gallery/migrations/0006_photo_client_upload_id.py` (`AddField` +
  `AddConstraint`, nothing else); do not hand-edit it
- [X] T011 [P] Migration test in
  `server/features/gallery/tests/integration/test_client_upload_id_migration.py`
  (`@pytest.mark.django_db(transaction=True)`, same style as `test_member_tag_migrations.py`):
  migrate to 0005, create photos, migrate to 0006 → rows kept with `NULL`; migrate back to 0005
  → rows kept
- [X] T012 In `server/features/gallery/dtos/gallery_dtos.py`: `NewPhoto` gains
  `client_upload_id: str | None = None`; new `ClientUploadMatch(StrictBaseModel)` with
  `photo_id: int`, `trashed: bool` and a docstring
- [X] T013 In `server/features/gallery/repositories/interfaces.py`, `GalleryRepository` gains
  `find_client_upload(self, client_upload_id: str) -> ClientUploadMatch | None`; document on
  `create_photo` that it raises `ClientUploadIdTakenError`. In the same commit, extend
  `FakeGalleryRepository` in `server/features/gallery/tests/fakes.py`: store
  `client_upload_id` per created photo and a trashed flag (`trash(photo_id)` helper), implement
  `find_client_upload`, raise `ClientUploadIdTakenError` from `create_photo` on a duplicate id,
  and a switch `competing_upload: NewPhoto | None` that, when set, inserts that photo first and
  then raises `ClientUploadIdTakenError` (a concurrent winner, research R-10)
- [X] T014 In `server/features/gallery/repositories/gallery_repository.py`: `create_photo` writes
  `client_upload_id`, catches `IntegrityError` around the insert inside its `atomic()` and raises
  `ClientUploadIdTakenError` when `Photo.all_objects` now has a row with that id, otherwise
  re-raises; new `find_client_upload` reading `Photo.all_objects.filter(client_upload_id=...)
  .values_list("pk", "deleted_at").first()`. Comment citing specs/016 R-03/R-04 on why
  `all_objects` and why the row check instead of the constraint name
- [X] T015 Integration tests in `server/features/gallery/tests/integration/test_gallery_repository.py`:
  id written on insert; `find_client_upload` returns live and trashed matches and `None` for an
  unknown id; second insert with the same id raises `ClientUploadIdTakenError` and leaves one
  row; two inserts without an id both succeed; the id is not in `PhotoView`

**Checkpoint**: schema, rules and repository ready.

---

## Phase 3: User Story 1 - A retried upload does not duplicate the photo (Priority: P1) 🎯 MVP

**Goal**: a repeat with a live original answers `201` with it and stores nothing; a trashed
original answers `409`.

**Independent Test**: upload twice with one id → one photo, both answers carry it.

- [X] T016 [P] [US1] Service unit tests in
  `server/features/gallery/tests/unit/test_upload_dedup.py` with the fakes from
  `server/features/gallery/tests/fakes.py`: first upload with an id stores it and returns what the
  no-id upload returns; repeat returns the same photo id, `rejected == []`, and the fake storage,
  image processor and album repository record no call (no file, no thumbnail, no cover, no
  album lookup); repeat with an invalid file still returns the original; repeat with an unknown
  `album_id` returns the original in its current album; trashed original raises
  `UploadedPhotoTrashedError`; after the fake purges the row the id is a first upload
- [X] T017 [US1] In `server/features/gallery/services/gallery_service.py`, `upload_photos` gains
  `client_upload_id: str | None = None` (docstring updated with an example). With an id: call
  `ensure_valid_client_upload(client_upload_id, len(files))`, then `_existing_upload` (lookup;
  live → `UploadResult(accepted=[view])`, trashed → raise `UploadedPhotoTrashedError`), before
  `_require_album`; no match → the existing path with the id carried into `NewPhoto` through
  `_store_one` / `_persist`. Without an id the path is byte-for-byte the 013 one. Keep every
  function 4–20 lines
- [X] T018 [US1] In `server/features/gallery/views/gallery.py`, `PhotoListAPIView.post` reads
  `optional_single_value(request.data.getlist("client_upload_id"), "client_upload_id")` after
  the `album_id` and file checks and passes it to `upload_photos`; status logic unchanged (a
  dedup result has no `rejected`, so `201`); docstring cites specs/016
- [X] T019 [US1] API tests in `server/features/gallery/tests/integration/test_upload_idempotency_api.py`: same
  id twice → both `201`, same `accepted[0].id`, `GET /api/albums/{id}/photos/` lists it once,
  file count under the media root unchanged by the second call; photo moved (PATCH `album_id`)
  then retried into the old album → `201` with the new `album_id`; retried into a nonexistent
  album → `201`; photo deleted then retried → `409` `CONFLICT`, Portuguese detail,
  `client_upload_id` in body, no `photo_id`; photo restored then retried → `201`; the Photo
  resource keys are exactly those of 015 (no `client_upload_id`); caller without `manage` → `403`
  before any id check

**Checkpoint**: MVP — retries no longer duplicate photos.

---

## Phase 4: User Story 2 - Two simultaneous retries still make one photo (Priority: P1)

**Goal**: the unique constraint decides; the loser leaves nothing and answers as a repeat.

**Independent Test**: the fake's `competing_upload` switch → one photo, loser's files deleted,
answer carries the winner.

- [X] T020 [P] [US2] Unit tests in `server/features/gallery/tests/unit/test_upload_dedup.py`:
  with `competing_upload` set, `upload_photos` returns the competing photo, the fake storage
  holds no file written by the losing request, the album gets no cover from the loser; with the
  competitor trashed before the retry lookup → `UploadedPhotoTrashedError`
- [X] T021 [US2] In `server/features/gallery/services/gallery_service.py`, `_store_first` wraps
  the store of the single file: catch `ClientUploadIdTakenError` (files already removed by
  `_persist`), re-run the lookup and answer as in T017 (live → result, trashed → `409`); a
  lookup that finds nothing re-raises (not a race, a bug). Comment citing specs/016 R-04
- [X] T022 [US2] Integration test in `server/features/gallery/tests/integration/test_upload_idempotency_api.py`:
  pre-insert a photo carrying the id through the repository while patching
  `GalleryRepositoryImpl.find_client_upload` to miss once (simulated lost race on SQLite) →
  `201` with the pre-inserted photo, one row with the id, no orphan file under the media root

**Checkpoint**: race safe.

---

## Phase 5: User Story 3 - Uploads without an id behave as today (Priority: P1)

**Goal**: no regression for tooling and the Django admin upload page.

**Independent Test**: existing upload tests pass unchanged.

- [X] T023 [P] [US3] Regression tests in `server/features/gallery/tests/integration/test_upload_idempotency_api.py`:
  multi-file upload without an id → `201`/`207` as in 013; same file twice without an id → two
  photos; a photo uploaded without an id never matches a later request with an id
- [X] T024 [P] [US3] Regression test in
  `server/features/gallery/tests/unit/test_upload.py` (the admin upload page stores photos with
  `client_upload_id` `NULL`) and `server/features/gallery/tests/integration/test_gallery_admin.py`
  (the photo change page neither shows nor changes `client_upload_id`)
- [X] T025 [US3] Run the 013/014/015 upload and admin tests unchanged:
  `python -m pytest features/gallery -q` — all pass with no edit to existing assertions

---

## Phase 6: User Story 4 - A malformed id is refused clearly (Priority: P2)

**Goal**: `400` naming the field and the expected shape; nothing stored.

**Independent Test**: each malformed variant → `400`, photo count unchanged.

- [X] T026 [US4] API tests in `server/features/gallery/tests/integration/test_upload_idempotency_api.py`: 65
  characters, empty value, value with a space, value `ç` → `400` `VALIDATION_ERROR` with
  `client_upload_id` and `expected`; id with two files → `400` with `file_count: 2`; field sent
  twice → `400` naming it; missing `album_id` with an id → the 013 `400`; after each, photo count
  unchanged and no file written

---

## Phase 7: User Story 5 - A deduplicated upload is visible in the logs (Priority: P3)

**Goal**: one structured line per deduplicated or trashed-original answer.

**Independent Test**: `caplog` on a repeat → one `gallery_upload_deduplicated`.

- [X] T027 [P] [US5] Unit tests in `server/features/gallery/tests/unit/test_upload_dedup.py` with
  `caplog`: repeat (fast path) and lost race each log one `gallery_upload_deduplicated` with
  `photo_id` and `actor_id` (string UUID); trashed original logs one
  `gallery_upload_original_trashed`; first upload logs neither; no filename or name in the
  record's extra fields
- [X] T028 [US5] In `server/features/gallery/services/gallery_service.py`, add
  `logger = logging.getLogger("features.gallery")` and emit the two events from the single
  helper that answers an existing upload (fast path and race share it), `extra={"photo_id",
  "actor_id"}`

---

## Phase 8: Polish & Cross-Cutting Concerns

- [X] T029 Check sizes and style: `server/features/gallery/services/gallery_service.py` under
  500 lines and every new function 4–20 lines; `black`, `ruff`, `mypy`, `bandit` via pre-commit on
  the changed files
- [X] T030 Full suite: `python -m pytest -q` from `server/`
- [ ] T031 Quickstart §2 (manual `curl` twice, then delete and retry → `409`) and §3 (parallel
  race on the PostgreSQL dev stack) from `specs/016-photo-upload-idempotency/quickstart.md`
- [ ] T032 Quickstart §4: migrate 0006 → 0005 → 0006 on a restored production dump; photo count
  unchanged, every existing row `NULL`
- [X] T033 Re-read `specs/gallery/spec.md` and the 013 contract against the code; fix any drift in
  the same commit

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (T001–T002)**: none; committed with the first code step.
- **Foundational (T003–T015)**: T005 needs T003; T009 → T010 → T011; T012 → T013 → T014 → T015.
  Blocks every story.
- **US1 (T016–T019)**: after Foundational. T017 → T018 → T019.
- **US2 (T020–T022)**: after T017 (shares the service branch).
- **US3 (T023–T025)**: after T018; independent of US2.
- **US4 (T026)**: after T018.
- **US5 (T027–T028)**: after T021 (the helper shared by fast path and race).
- **Polish (T029–T033)**: after all stories.

### Within Each Story

Tests written first and failing, then implementation; service before view.

### Parallel Opportunities

- T003/T005/T007 (different files) and their tests T004/T006/T008.
- T011 alongside T012–T015 once T010 is done.
- T016 alongside T017 (test file vs service file).
- US3 (T023, T024) and US4 (T026) alongside US2 once T018 is done — T023 and T026 share
  `test_upload_idempotency_api.py`, so one after the other.

---

## Parallel Example: Foundational

```text
Task: "T003 exceptions in server/core/domain/gallery_exceptions.py"
Task: "T005 rules in server/features/gallery/domain/upload_rules.py"
Task: "T007 optional_single_value in server/core/http/parsing.py"
```

## Parallel Example: User Story 1

```text
Task: "T016 service unit tests in server/features/gallery/tests/unit/test_upload_dedup.py"
Task: "T017 dedup branch in server/features/gallery/services/gallery_service.py"
```

---

## Implementation Strategy

### MVP First (User Story 1)

1. Phase 1 + Phase 2.
2. Phase 3 (US1) → validate with quickstart §2. Plain retries stop duplicating.

### Incremental Delivery

1. US1 → US2 (race) → US3 (regression proof) → US4 (errors) → US5 (logs).
2. Commits follow the plan's steps, each type-correct for the whole-tree mypy hook; the spec
   updates (T001–T002) go in the first code commit.
