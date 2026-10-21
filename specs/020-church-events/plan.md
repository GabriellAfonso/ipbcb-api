# Implementation Plan: Church Events

**Branch**: `020-church-events` | **Date**: 2026-10-21 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/020-church-events/spec.md`

## Summary

A new feature app `features/events` with one model (`Event`), public reads (`api/events/`,
`api/events/{id}/`, open to anonymous callers, members also see `members` events) and management
CRUD under `api/admin/events/` gated by scope `events`. "Active" is a date filter computed per
request in `America/Sao_Paulo` from an injected clock — nothing stored, no job.

The image is validated by content (format, size, pixels, minimum size, 16:9 ± 2% after EXIF
orientation), re-encoded to a JPEG fitted within 1920 × 1080 and stored as `events/{uuid}.jpg`.
To do this without a cross-feature import, the gallery's image processor moves to
`core/files/imaging/` (R-01) and gains two methods.

The media access check gets an `events/` folder whose rule is the first one that admits anonymous
callers: a public event's image to anyone, a members event's image to members only, everything
else `404` — decided by one indexed lookup through a port the events app implements (R-05).

A data migration raises Liderança and Mídia to `owner` on `events`. Specs 012, 009, the
constitution and the domain docs are updated in the same commit as the code.

## Technical Context

**Language/Version**: Python 3.14, Django 6.0.8

**Primary Dependencies**: DRF 3.17.2, SimpleJWT, Pydantic 2.12.5, `dependency-injector` 4.48.3,
drf-spectacular 0.29.0, Pillow. No new dependency

**Storage**: PostgreSQL (prod), SQLite (tests); image files on Django default storage under
`MEDIA_ROOT/events/`

**Testing**: pytest + pytest-django from `server/`; unit tests with named fakes
(`features/events/tests/fakes.py`), integration tests through `APIClient` with a temp
`MEDIA_ROOT`

**Target Platform**: Linux container behind nginx at `/ipbcb/`

**Project Type**: web service (REST API for the Android app)

**Performance Goals**: list = one query (with `select_related`); media check for `events/` = one
indexed lookup

**Constraints**: functions 4–20 lines, files < 500 lines, no cross-feature imports, no
`.raw()`, ETag/304 on reads

**Scale/Scope**: tens of events per year; images ≤ 1920 × 1080 JPEG

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Rule | How this plan complies |
|------|------------------------|
| No endpoint bypasses auth unless explicitly marked public | Public list/detail are `AllowAny`, declared public in spec FR-008 and `specs/events/spec.md`. Management views `IsAuthenticated` + `scope_permission(Scope.EVENTS)` |
| Media served only through the access check, default deny | Still true. `events/` is a new rule in the same check; it admits anonymous callers **only** for public event images. **Amendment** of the constitution's Media section (spec FR-025) — see Complexity Tracking |
| Input validated before storage | DRF serializers for fields; `EventImagePreparer` for the file by decoded content; Pydantic DTOs into the service |
| ORM only, no queries in loops | `EventRepositoryImpl` only; `select_related("created_by__profile", "updated_by__profile")` |
| Features never import each other | Image processor moved to `core/files/imaging` (R-01); media ↔ events through a port wired in `config/di.py` (R-05). Events read the creator's and last editor's names by ORM relation, no `features.accounts` import |
| Views → Services → Repositories | Views call `EventService` / `EventWriteService` only |
| Services never import HTTP objects | Views pass streams and DTOs; services raise domain exceptions |
| DI via container; DTOs not dicts | New providers in `config/di.py`; Pydantic DTOs (data-model.md) |
| Domain errors in `core/domain/` | `core/domain/event_exceptions.py`, re-exported (R-12) |
| Caching | Public and management reads `private, no-store` + `Vary: Authorization` (body depends on the caller); media keeps its own exception |
| Migrations | `events/0001` by `makemigrations`; `core/0008` data migration with reason on top (R-11) |
| Models have `__str__`, `Meta.ordering`, `verbose_name` | `Event` has them |
| Specs and code in the same commit | spec/plan/tasks, `specs/events/spec.md`, 012, 009, constitution, `docs/features/events.md`, `docs/features/media.md` |

**Gate**: PASS with one justified amendment (Complexity Tracking). Re-checked after Phase 1: PASS.

## Project Structure

### Documentation (this feature)

```text
specs/020-church-events/
├── spec.md
├── plan.md              # this file
├── research.md          # R-01 … R-13
├── data-model.md
├── quickstart.md
├── contracts/
│   └── events-api.md
├── checklists/
│   └── requirements.md
└── tasks.md             # /speckit-tasks
```

### Source Code

```text
server/
├── config/
│   ├── settings/base.py                  # + "features.events" in INSTALLED_APPS
│   ├── urls.py                           # + include("features.events.urls")
│   └── di.py                             # + events providers; image_processor import moves; media gets event_image_lookup
├── core/
│   ├── domain/event_exceptions.py        # new (R-12); re-exported by exceptions.py
│   ├── files/imaging/                    # moved from features/gallery/imaging (R-01)
│   │   ├── interfaces.py                 #   + upright_dimensions, fitted_jpeg
│   │   └── pillow_image_processor.py
│   ├── migrations/0008_events_owner_for_leader_media.py
│   └── tests/…/test_pillow_image_processor.py   # moved with the processor, + new methods
├── features/gallery/services/…           # import path of ImageProcessor only
├── features/media/
│   ├── domain/media_rules.py             # + "events" rule, MediaAudience.EVENT_VISIBILITY
│   ├── repositories/interfaces.py        # + EventImageLookup port
│   ├── services/media_access_service.py  # + _check_event_image
│   ├── views/media_file.py               # IsAuthenticatedOrEventImage; anonymous viewer
│   └── tests/…                           # + events/ cases
└── features/events/
    ├── apps.py, urls.py
    ├── models/event.py
    ├── migrations/0001_initial.py
    ├── domain/event_dates.py, event_image_rules.py, event_enums.py
    ├── dtos.py
    ├── repositories/interfaces.py, event_repository.py, event_image_storage.py, event_image_lookup.py
    ├── services/event_service.py, event_write_service.py, event_image_preparer.py
    ├── serializers.py
    ├── views/public_events.py, admin_events.py
    └── tests/fakes.py, images.py, unit/…, integration/…

docs/features/events.md                   # new
docs/features/media.md                    # + events/ rule
specs/events/spec.md                      # domain spec, current state
specs/012-…/spec.md, specs/009-…/spec.md, specs/constitution.md   # amendments
```

**Structure Decision**: one new feature app shaped like `features/members`. Outside it: the
processor move (mechanical), the media rule, one data migration, registration (settings, urls,
di), and doc amendments.

## Implementation Order

1. **Processor move** (`git mv`, import updates, gallery tests green) + the two new methods with
   their tests.
2. **Events core**: exceptions, domain, model + `makemigrations`, DTOs, repositories, services,
   unit tests on fakes.
3. **HTTP**: serializers, views, urls, DI, settings; integration tests (public, management,
   permissions matrix, image rules, clock edges).
4. **Permissions**: `core/0008` + test that Leader/Media hold `events__owner` only.
5. **Media**: port, rule, permission class, anonymous viewer; tests for the access table.
6. **Docs/specs**: domain spec, feature doc, 012/009/constitution amendments.
7. Full suite, mypy, `makemigrations --check`, schema validation.

Commits: docs-only first if split; then code + tests that must move together (mypy hook checks
the whole tree).

## Complexity Tracking

| Violation | Why needed | Simpler alternative rejected because |
|-----------|------------|--------------------------------------|
| Media check admits an anonymous caller for `events/` (constitution Media: "authenticated access check") | Visitors without an account must see public event images (spec FR-019, agreed with the app) | A separate unauthenticated media route would duplicate path validation (009's main safeguard); making the folder members-only breaks the visitors' carousel |
