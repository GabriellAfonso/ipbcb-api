# Implementation Plan: Idempotent Photo Upload

**Branch**: `016-photo-upload-idempotency` | **Date**: 2026-09-29 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/016-photo-upload-idempotency/spec.md`

## Summary

`POST /api/photos/` accepts an optional `client_upload_id`, so the app's retry queue can resend a
photo without creating a second one.

`Photo` gains a nullable `client_upload_id` (64 chars, `editable=False`) under a named unique
constraint over all rows. The view checks that the field is sent at most once; the service checks
its shape and that exactly one file came with it, then looks the id up in `Photo.all_objects`
**before** checking the album: a live original is returned as the upload's result (`201`, same
body shape), a trashed one is refused with `409` `CONFLICT`, and no row means the 013 upload path,
which now stores the id. The unique constraint decides races: the repository turns the
`IntegrityError` into a domain exception, `_persist` already removes the loser's files, and the
service answers the loser as a repeat. Two log lines, ids only. One generated migration.

## Technical Context

**Language/Version**: Python 3.14, `.venv_windows`

**Primary Dependencies**: Django 6.0, DRF 3.17, dependency-injector, Pydantic 2.12. No new
dependency.

**Storage**: PostgreSQL in production, SQLite in tests. One generated migration,
`gallery/0006` (R-09). No data migration.

**Testing**: pytest + pytest-django; `FakeGalleryRepository` in
`features/gallery/tests/fakes.py` extended with an id index and a lost-race switch (R-10); mypy,
ruff, bandit.

**Target Platform**: Linux container behind nginx, prefix `/ipbcb/`.

**Project Type**: Web service (REST API), single Android client.

**Performance Goals**: a repeat costs one indexed lookup plus the usual resource read, and no
image processing or file write (SC-005); a first upload with an id costs the same as today plus
the index entry.

**Constraints**: no change to the Photo resource, the feed, the trash, tags or other endpoints
(FR-018); the admin upload page untouched (FR-016); services never see HTTP; ORM and
`IntegrityError` only in repositories; migrations 0001–0005 untouched; files under 500 lines.

**Scale/Scope**: low thousands of photos; one endpoint-method changed, one field, one constraint.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design; result unchanged.*

| Rule (`specs/constitution.md`, `CLAUDE.md`) | Status |
|---|---|
| `IsAuthenticated` + scope on the write | ✅ unchanged `GALLERY_WRITE`; permission before any id check |
| Views → services → repositories; ORM only in repositories | ✅ lookup and constraint handling in `GalleryRepositoryImpl`; `IntegrityError` never leaves it (R-04) |
| Services never import HTTP objects | ✅ the service receives `client_upload_id: str | None` and the file list |
| Input validated before the database | ✅ `optional_single_value` in the view, `upload_rules.py` in the service, both before the lookup (R-02, R-05) |
| Domain exceptions with offending value and expected shape | ✅ 4 new exceptions in `core/domain/gallery_exceptions.py`, re-exported (R-05, R-06) |
| DI via `config/di.py` | ✅ no new provider: `GalleryService` and its repository already wired |
| DTOs are Pydantic | ✅ `ClientUploadMatch`; `NewPhoto` + field |
| No queries in loops | ✅ one lookup per request |
| Structured JSON logs, ids only | ✅ R-07 |
| Models: `__str__`, `Meta.ordering`, `verbose_name` | ✅ unchanged on `Photo` |
| Migrations generated; applied ones untouched | ✅ one generated `AddField` + `AddConstraint`; production-dump round trip anyway (quickstart §4) |
| Spec before code; spec and code in the same commit | ✅ step 0 |
| Functions 4–20 lines, files < 500 lines | ✅ `gallery_service.py` ≈ 275 lines after; rules in their own module |
| Tests for every new function; named fakes | ✅ quickstart §1 |

Gate: **pass**. No deviations.

## Technical Decisions

Full reasoning in [research.md](research.md).

- **D-1** Nullable `client_upload_id` CharField(64), `editable=False`, named unique constraint over
  all rows (R-01).
- **D-2** Check order: permission → view shape (`album_id`, file present, id once) → service
  rules (format, one file) → id lookup → album and the 013 path (R-02).
- **D-3** Fast path through `find_client_upload` on `Photo.all_objects` (R-03).
- **D-4** Race decided by the constraint; `ClientUploadIdTakenError` from the repository; files
  cleaned by the existing `_persist` rollback (R-04).
- **D-5** Pure rules in `domain/upload_rules.py`, English messages, echoed value truncated (R-05).
- **D-6** `UploadedPhotoTrashedError(ConflictError)`, Portuguese, only `client_upload_id` in the
  body (R-06).
- **D-7** Two log lines from `GalleryService` (R-07).
- **D-8** Everything stays in `GalleryService`; admin page unchanged (R-08).
- **D-9** Race covered by a fake and a repository test; real concurrency checked by hand on
  PostgreSQL (R-10).

## Spec adjustments made while planning

Recorded in the spec's Clarifications, same commit:

- FR-009: "no file read" becomes "the file is never examined". The multipart parser receives the
  whole body before the view runs; what the repeat skips is validation, pixel check, thumbnail,
  EXIF and every write.
- `specs/gallery/spec.md`: the list of code allowed to read `all_objects` gains the upload
  deduplication lookup (FR-020).

## Service split

| Unit | Change |
|------|--------|
| `GalleryService.upload_photos` | + `client_upload_id: str | None = None`; with an id: rules → `_existing_upload` → `_store_first` (catches `ClientUploadIdTakenError`, re-looks up) → `_answer_existing` (live view or `409`, logs) |
| `GalleryRepositoryImpl` | + `find_client_upload`; `create_photo` writes the id and maps the constraint violation |
| `PhotoListAPIView.post` | reads `client_upload_id` through `optional_single_value`, passes it on; status logic unchanged |
| `features/gallery/domain/upload_rules.py` (new) | `CLIENT_UPLOAD_ID_MAX_LENGTH`, `ensure_valid_client_upload(client_upload_id, file_count)` |
| `core/http/parsing.py` | + `optional_single_value(values, field) -> str | None` |
| `views/upload.py` (admin page) | unchanged |

## Implementation Order

Each step leaves the tree type-correct for the whole-tree mypy hook (memory: commit splitting).

0. **Specs** (in the commit with the first code step, CLAUDE.md §6.2): `specs/gallery/spec.md`
   (Photo field and constraint, `all_objects` users, `POST /api/photos/` field, outcomes and
   dedup rules, errors table, log lines); the 013 contract section from
   [contracts/photo-upload-api.md](contracts/photo-upload-api.md); the spec adjustments above;
   `tasks.md`.
1. **Exceptions**: the 4 exceptions in `core/domain/gallery_exceptions.py`, re-exported from
   `core/domain/exceptions.py`; unit tests (status, `extra_context`, messages).
2. **Rules and parsing**: `domain/upload_rules.py`, `optional_single_value`; unit tests.
3. **Model + migration**: `Photo.client_upload_id` and the constraint;
   `makemigrations gallery`; migration round-trip test.
4. **Repository**: `ClientUploadMatch`, `NewPhoto.client_upload_id`, Protocol methods,
   `find_client_upload`, `create_photo` mapping; fake updated in the same step; integration tests.
5. **Service**: dedup branch, race handling, log lines; unit tests with the fakes.
6. **View**: read and pass the id; API tests (US1–US4, id absent from the resource, no-id
   regression, admin page regression).
7. **Validation**: quickstart §1–§4, §3 on the PostgreSQL dev stack, §4 on the production dump.

## Project Structure

### Documentation (this feature)

```text
specs/016-photo-upload-idempotency/
├── spec.md
├── plan.md                        # this file
├── research.md                    # R-01 … R-10
├── data-model.md
├── quickstart.md
├── contracts/photo-upload-api.md
├── checklists/requirements.md
└── tasks.md                       # /speckit-tasks
```

### Source Code

```text
server/
├── core/
│   ├── domain/
│   │   ├── exceptions.py                          # re-export the 4 new exceptions
│   │   └── gallery_exceptions.py                  # + 4 exceptions
│   ├── http/parsing.py                            # + optional_single_value
│   └── tests/unit/…                               # parsing guards, gallery exceptions
└── features/gallery/
    ├── domain/upload_rules.py                     # new
    ├── dtos/gallery_dtos.py                       # NewPhoto + field, ClientUploadMatch
    ├── migrations/0006_photo_client_upload_id.py  # generated
    ├── models/gallery.py                          # Photo.client_upload_id + constraint
    ├── repositories/
    │   ├── interfaces.py                          # GalleryRepository + find_client_upload
    │   └── gallery_repository.py                  # lookup, id on insert, violation mapping
    ├── services/gallery_service.py                # dedup branch, race, logs
    ├── views/gallery.py                           # PhotoListAPIView.post reads the id
    └── tests/                                     # per quickstart §1; fakes.py extended
```

**Structure Decision**: the change stays inside the existing upload use case in
`features/gallery`, layer by layer as in 013–015; the only new module is the pure rules file. No
cross-feature link, no new DI provider.

## Dependencies (outside this repository)

- **Android app** (separate spec): generates the UUID per queued photo, sends it on every retry,
  and drops the item with the server's message on `409`. Not required for the backend to ship:
  requests without the field behave as today.

## Out of scope, found during planning (reported, not changed)

- The multipart body of a repeat is still uploaded in full by the phone; skipping the upload
  itself would need a separate "does this id exist" call, which the spec leaves out.
- Tests run on SQLite, so the real concurrent race is verified by hand (R-10), not in CI.

## Complexity Tracking

No constitution violations to justify.
