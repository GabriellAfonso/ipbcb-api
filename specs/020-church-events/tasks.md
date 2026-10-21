# Tasks: Church Events

**Input**: Design documents from `specs/020-church-events/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/events-api.md

**Tests**: required (CLAUDE.md §10: every new function gets a test; fakes are named classes).

Paths are relative to the repository root; Python code lives under `server/`.

## Phase 1: Setup

- [X] T001 Move `server/features/gallery/imaging/` to `server/core/files/imaging/` with `git mv` and update imports in `server/config/di.py`, `server/features/gallery/services/album_cover_service.py`, `server/features/gallery/services/gallery_service.py`; move `server/features/gallery/tests/integration/test_pillow_image_processor.py` to `server/core/tests/integration/test_pillow_image_processor.py` (R-01)
- [X] T002 Add `upright_dimensions` and `fitted_jpeg` to `server/core/files/imaging/interfaces.py` and `server/core/files/imaging/pillow_image_processor.py` (R-02, R-03), with tests in `server/core/tests/integration/test_pillow_image_processor.py`
- [X] T003 Create the app skeleton `server/features/events/` (`__init__.py`, `apps.py`, `urls.py`, `models/`, `domain/`, `repositories/`, `services/`, `views/`, `migrations/`, `tests/unit/`, `tests/integration/`) and register `features.events` in `server/config/settings/base.py`

## Phase 2: Foundational (blocks every story)

- [X] T004 [P] Create `server/core/domain/event_exceptions.py` (`EventNotFoundError`, `EventImageInvalidError`, `EventImageMissingError`, `EventDatesInvalidError`, `EventStatusFilterError`, field errors through `extra_context`) and re-export from `server/core/domain/exceptions.py`; tests in `server/core/tests/unit/test_event_exceptions.py`
- [X] T005 [P] Create `server/features/events/domain/event_enums.py` (`EventVisibility`, `EventStatusFilter`, `parse_status_filter`) and `server/features/events/domain/event_dates.py` (`EVENTS_TIME_ZONE`, `today_in_events_zone`, `last_day`, `ensure_dates_ordered`); tests in `server/features/events/tests/unit/test_event_domain.py`
- [X] T006 [P] Create `server/features/events/domain/event_image_rules.py` (limits, `ensure_event_image_shape`, `ensure_event_image_extension`); tests in `server/features/events/tests/unit/test_event_image_rules.py`
- [X] T007 Create `Event` in `server/features/events/models/event.py` per data-model.md and generate `server/features/events/migrations/0001_initial.py` with `makemigrations`
- [X] T008 Create DTOs in `server/features/events/dtos.py` (`EventCreatorDTO`, `EventRecordDTO`, `EventCreateDTO`, `EventPatchDTO`); tests in `server/features/events/tests/unit/test_event_dtos.py`
- [X] T009 Create protocols in `server/features/events/repositories/interfaces.py` (`EventRepository`, `EventImageStorage`) and named fakes in `server/features/events/tests/fakes.py` (`FakeEventRepository`, `FakeEventImageStorage`, `FakeImageProcessor`, `FixedClock`)
- [X] T010 Implement `EventRepositoryImpl` in `server/features/events/repositories/event_repository.py` and `DefaultStorageEventImageStorage` in `server/features/events/repositories/event_image_storage.py`; tests in `server/features/events/tests/integration/test_event_repository.py`
- [X] T011 Create test helpers in `server/features/events/tests/images.py` (real encoded images of a given size/format/EXIF orientation) and `server/features/events/tests/integration/conftest.py` (temp `MEDIA_ROOT`, pinned clock override)

## Phase 3: User Story 1 — Anyone sees upcoming events (P1) 🎯 MVP

**Goal**: anonymous `GET api/events/` and `GET api/events/{id}/` return active public events in order; public images load without a token.

**Independent test**: seed past/ongoing/future public events; list anonymously; check order, detail `404` for past, image served with no token.

- [X] T012 [US1] Implement `EventService.list_visible` / `get_visible` in `server/features/events/services/event_service.py`; unit tests with fakes in `server/features/events/tests/unit/test_event_service.py` (order, midnight edges, past `404`)
- [X] T013 [US1] Public serializer `EventPublicSerializer` in `server/features/events/serializers.py` (absolute `image_url`, `HH:MM` time)
- [X] T014 [US1] Views `PublicEventListAPIView`, `PublicEventDetailAPIView` in `server/features/events/views/public_events.py` (`AllowAny`, membership flag, private ETag response), routes in `server/features/events/urls.py`, include in `server/config/urls.py`, providers and wiring in `server/config/di.py`
- [X] T015 [US1] Media: port `EventImageLookup` in `server/features/media/repositories/interfaces.py`; `events` rule and `MediaAudience.EVENT_VISIBILITY` in `server/features/media/domain/media_rules.py`; `_check_event_image` in `server/features/media/services/media_access_service.py`; `IsAuthenticatedOrEventImage` and anonymous viewer in `server/features/media/views/media_file.py`
- [X] T016 [US1] Implement `EventImageLookupImpl` in `server/features/events/repositories/event_image_lookup.py` and wire it into `media_access_service` in `server/config/di.py`
- [X] T017 [P] [US1] Media tests: update `server/features/media/tests/fakes.py` and `server/features/media/tests/unit/test_media_access_service.py`, `test_media_rules.py`; add `server/features/media/tests/integration/test_media_event_images_api.py` (access table of the contract, other folders still `401` anonymously)
- [X] T018 [US1] Integration tests `server/features/events/tests/integration/test_public_events_api.py` (scenarios US1 1–6)

## Phase 4: User Story 2 — Members also see members-only events (P1)

**Goal**: members get `members` events; everyone else never learns they exist.

**Independent test**: one public + one members event; list/detail/image as anonymous, non-member with role, member, invalid token.

- [X] T019 [US2] Integration tests in `server/features/events/tests/integration/test_public_events_visibility_api.py` (scenarios US2 1–5, no-profile user, identical 404 bodies)
- [X] T020 [US2] Members-image cases in `server/features/media/tests/integration/test_media_event_images_api.py` (member `200`, non-member `404`, invalid token `401`)

## Phase 5: User Story 3 — The panel creates an event (P1)

**Goal**: `POST api/admin/events/` with image validation and processing.

**Independent test**: as Mídia, create with only required fields → `201`, visible publicly, stored JPEG ≤ 1920×1080.

- [X] T021 [US3] `EventImagePreparer` in `server/features/events/services/event_image_preparer.py`; unit tests `server/features/events/tests/unit/test_event_image_preparer.py` (order of checks, GIF refused, EXIF-rotated ratio)
- [X] T022 [US3] `EventWriteService.create_event` in `server/features/events/services/event_write_service.py` (file cleanup on failure); unit tests `server/features/events/tests/unit/test_event_write_service.py`
- [X] T023 [US3] Serializers `EventWriteSerializer` (create/patch input) and `EventRecordSerializer` in `server/features/events/serializers.py`
- [X] T024 [US3] `AdminEventListAPIView.post` in `server/features/events/views/admin_events.py` (multipart, `scope_permission(Scope.EVENTS)`), routes and DI
- [X] T025 [US3] Data migration `server/core/migrations/0008_events_owner_for_leader_media.py` (R-11) with test `server/core/tests/integration/test_events_owner_migration.py`
- [X] T026 [US3] Integration tests `server/features/events/tests/integration/test_admin_events_create_api.py` (scenarios US3 1–8, role matrix for POST)

## Phase 6: User Story 4 — Edit and delete (P2)

**Goal**: `PATCH` (image optional, merged date rule) and `DELETE` (hard, owner).

**Independent test**: patch end_date + image → new URL, old file gone; delete → `204`, gone everywhere.

- [X] T027 [US4] `EventWriteService.update_event` / `delete_event` in `server/features/events/services/event_write_service.py`; unit tests in `server/features/events/tests/unit/test_event_write_service.py`
- [X] T028 [US4] `AdminEventDetailAPIView.patch` / `delete` in `server/features/events/views/admin_events.py`
- [X] T029 [US4] Integration tests `server/features/events/tests/integration/test_admin_events_edit_api.py` (scenarios US4 1–9)

## Phase 7: User Story 5 — Review all events (P2)

**Goal**: management list with `status` filter and detail of any event.

**Independent test**: active and past events of both visibilities; list with each status.

- [X] T030 [US5] `EventService.list_for_management` / `get_for_management` in `server/features/events/services/event_service.py`; unit tests in `server/features/events/tests/unit/test_event_service.py`
- [X] T031 [US5] `AdminEventListAPIView.get`, `AdminEventDetailAPIView.get` in `server/features/events/views/admin_events.py` (distinct `operation_id`s)
- [X] T032 [US5] Integration tests `server/features/events/tests/integration/test_admin_events_read_api.py` (scenarios US5 1–4, role matrix for GET)

## Phase 8: Polish & Cross-Cutting

- [X] T033 [P] Domain spec `specs/events/spec.md` (current state + Future) and feature doc `docs/features/events.md`
- [X] T034 [P] Amend `specs/012-feature-role-permissions/spec.md` (FR-024 list) and `specs/accounts/spec.md` if it names `events` as reserved
- [X] T035 [P] Amend `specs/009-protected-media-access/spec.md`, `specs/constitution.md` (Media), `docs/features/media.md` (FR-025)
- [X] T036 Run `mypy .`, `makemigrations --check --dry-run`, `spectacular --validate --fail-on-warn`, and the full pytest suite from `server/`; fix findings
- [X] T037 Mark completed tasks in this file and the checklist

## Dependencies

- Setup (T001–T003) → Foundational (T004–T011) → stories.
- US1 (T012–T018) is the MVP and provides the public service, serializer and media rule US2 relies on.
- US2 depends on US1 (same endpoints, extra cases).
- US3 depends on Foundational only; US4 depends on US3 (write service, serializers); US5 depends on US3 (record serializer).
- Polish after all stories.

## Parallel Opportunities

- T004, T005, T006 touch different files.
- T017 (media tests) alongside T018 (events tests) once T015–T016 exist.
- T033, T034, T035 are docs-only.

## Implementation Strategy

MVP = Phases 1–3 (public read with images). Then US2 (privacy), US3 (creation — the first time
the app can publish), US4, US5, Polish. Single commit set at the end, ordered so each commit
passes the whole-tree mypy hook.
