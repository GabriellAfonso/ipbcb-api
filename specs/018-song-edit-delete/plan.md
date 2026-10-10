# Implementation Plan: Edit and Delete Songs

**Branch**: `018-song-edit-delete` | **Date**: 2026-10-10 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/018-song-edit-delete/spec.md`

## Summary

Add `PATCH` and `DELETE` on a new detail route `api/songs/{id}/`, inside the existing `songs`
feature, with no schema change.

- **Edit** reuses the create rules. The field types become shared Pydantic `Annotated` types, and a
  new `SongChangesInput` uses them with every field optional and `null` rejected. The duplicate
  check runs only when the normalized title + artist pair changes, and excludes the song itself.
- **Delete** first measures the song's two `PROTECT` references (distinct play dates, setlist
  dates) and refuses with a pt-BR `SongInUseError` (`409`). The repository also translates a late
  `ProtectedError` or deferred-FK `IntegrityError` into the same error, so the race never becomes
  a 500.

Decisions and their reasons are in [research.md](research.md).

## Technical Context

**Language/Version**: Python 3.14 (Dockerfile), Django 6.0.8

**Primary Dependencies**: Django ORM, DRF 3.17.2, Pydantic 2.12.5 (DTOs), `dependency-injector` (`config/di.py`)

**Storage**: PostgreSQL in production, SQLite in-memory in tests. No migration

**Testing**: pytest + pytest-django, run from `server/`; named fakes in `features/songs/tests/fakes.py`

**Target Platform**: Linux container behind nginx at `/ipbcb/`

**Project Type**: web service (REST API for the Android app)

**Performance Goals**: constant query count per request (edit: lookup + at most one duplicate query + update; delete: lookup + 2 usage queries + cascade)

**Constraints**: no 5xx on any covered path, including the delete race; functions 4–20 lines; files under 500 lines

**Scale/Scope**: catalogue of a few hundred songs, one leader editing at a time

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Rule | How this plan complies |
|------|------------------------|
| `IsAuthenticated` on every authenticated view | `SongDetailAPI.permission_classes = [IsAuthenticated, scope_permission(Scope.SONGS)]` |
| One scope per management endpoint, level from method; overrides only raise | `songs`, no override: `PATCH` manage, `DELETE` owner. Nothing in `lowered=` |
| Input validated before reaching the DB | `SongChangesInput` (Pydantic, `extra="forbid"`) validates the body; `require_object_body` is not needed because `model_validate` rejects a non-object as `400` |
| ORM only, no queries in loops | two aggregate queries for usage; `update_fields` save |
| Error shape `{error_code, detail}` | domain exceptions through `build_canonical_error`; `extra_context` adds keys |
| Views → Services → Repositories → Models | view calls `SongService`; only `SongRepositoryImpl` imports models / `ProtectedError` / `IntegrityError` |
| Services never import HTTP objects | `SongService` receives DTOs and ids |
| Features never import each other | `SetlistItem` and `Played` are both in `features/songs` |
| DI via `config/di.py`; DTOs not dicts | existing `song_service` / `song_repository` providers; `SongChangesInput`, `SongUsage` DTOs |
| Caching: private only when body depends on caller | the responses do not depend on the caller; the cached public reads invalidate by body (R-08) |
| Code in English; user-facing text may be pt-BR | only `SongInUseError`'s message is pt-BR |

**Gate**: PASS. Re-checked after Phase 1: PASS, no new violations.

## Project Structure

### Documentation (this feature)

```text
specs/018-song-edit-delete/
├── plan.md              # this file
├── research.md          # R-01 … R-10
├── data-model.md        # DTOs, exceptions, entities touched
├── quickstart.md        # how to validate
├── contracts/
│   └── song-detail-api.md
├── checklists/
│   └── requirements.md
└── tasks.md             # /speckit-tasks
```

### Source Code

```text
server/
├── core/
│   ├── domain/exceptions.py                 # + SongNotFoundError, SongInUseError (+ message helper)
│   └── tests/integration/
│       └── test_management_access_matrix.py # + PATCH/DELETE api/songs/{id}/ rows
└── features/songs/
    ├── dtos.py                              # + _YoutubeLink, SongChangesInput, SongUsage; NewSongInput uses _YoutubeLink
    ├── repositories/
    │   ├── interfaces.py                    # SongRepository: song_exists(exclude_id), get_song_usage, update_song, delete_song
    │   └── song_repository.py               # implementations; race translation in delete_song
    ├── services/song_service.py             # + update_song, delete_song
    ├── views/songs.py                       # + SongDetailAPI
    ├── urls.py                              # + api/songs/<int:pk>/
    └── tests/
        ├── fakes.py                         # + FakeSongRepository (in-memory), RaisingDeleteSongRepository
        ├── unit/test_song_changes_input.py
        ├── unit/test_song_service_edit_delete.py
        ├── unit/test_song_in_use_error.py
        └── integration/test_song_detail_api.py

specs/
├── songs/spec.md                            # both endpoints under POST /api/songs/; SetlistItem/Played note
└── 012-feature-role-permissions/spec.md     # songs table: PATCH manage, DELETE owner (default)
```

**Structure Decision**: everything stays inside `features/songs`, next to `POST api/songs/`. The
only changes outside it are the two shared exceptions in `core/domain/exceptions.py` and the
access-matrix rows. No new DI provider (R-10).

## Implementation Order

1. **Exceptions**: `SongNotFoundError`, `SongInUseError` with the pt-BR message helper, plus unit
   tests of every wording row in the contract.
2. **DTOs**: extract `_YoutubeLink`; refactor `NewSongInput` (existing test unchanged, still green);
   add `SongChangesInput` and `SongUsage`, with unit tests.
3. **Repository**: extend the protocol and the implementation (`song_exists(..., exclude_id)`,
   `get_song_usage`, `update_song`, `delete_song` with race translation). Add the named fakes.
4. **Service**: `update_song(song_id, changes)` and `delete_song(song_id)`, with unit tests
   against the fakes.
5. **View + URL**: `SongDetailAPI`, route `api/songs/<int:pk>/`, integration tests (permissions,
   cascade, blocked delete untouched, real `ProtectedError` race, ETag invalidation).
6. **Specs**: `specs/songs/spec.md` and the spec 012 classification, plus the access-matrix rows.
   These go in the same commit as the code, per CLAUDE.md §6.2.

Each commit must leave the tree consistent for the mypy hook. Protocol, implementation and fakes
change together in step 3.

## Complexity Tracking

No constitution violation to justify.
