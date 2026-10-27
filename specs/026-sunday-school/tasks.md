# Tasks: Sunday School Lessons

**Input**: Design documents from `specs/026-sunday-school/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/api.md

**Tests**: required by `CLAUDE.md` §10 (every new function gets a test). Paths are relative to
`server/` unless they start with `specs/`.

## Phase 1: Setup

- [X] T001 Write the domain spec `specs/sunday-school/spec.md` (models, content schema, endpoints, rules, errors) and add `sunday_school` to the scope list in `specs/012-feature-role-permissions/spec.md`
- [X] T002 Create the app skeleton `features/sunday_school/{__init__.py,apps.py}` and register `features.sunday_school` in `config/settings/base.py`

## Phase 2: Foundational

- [X] T003 Add `Scope.SUNDAY_SCHOOL` in `core/domain/access.py`; generate `core/migrations/0013_alter_panelscope_options.py`; hand-write `core/migrations/0014_sunday_school_scope_for_leader.py` (copy of 0012); add the scope to the access matrix test
- [X] T004 [P] Create `core/domain/sunday_school_exceptions.py` (`SundaySchoolYearNotFoundError`, `SundaySchoolLessonNotFoundError`, `SundaySchoolContentInvalidError`, `SundaySchoolOrderMismatchError`) and re-export them in `core/domain/exceptions.py`
- [X] T005 [P] Add `verse_counts_by_book()` and `book_names()` to `features/bible/repositories/bible_text.py` (Protocol + impl, minimum across translations) with tests in `features/bible/tests/unit/test_bible_domain.py`
- [X] T006 [P] Create `features/sunday_school/domain/icons.py` (`LessonIcon`, `STANDARD_SECTION_ICONS`) and `features/sunday_school/domain/scripture_index.py` (`ScriptureIndex`: reference check, book check, `BookFactsDTO` lookup) with unit tests in `features/sunday_school/tests/unit/test_scripture_index.py`
- [X] T007 Create `features/sunday_school/content_schema.py` (ten blocks, discriminated union, limits) and `features/sunday_school/content_validation.py` (schema + scripture → `SundaySchoolContentInvalidError` with paths); unit tests in `features/sunday_school/tests/unit/test_content_schema.py`
- [X] T008 Create models `features/sunday_school/models/{__init__.py,year.py,lesson.py}` and generate `features/sunday_school/migrations/0001_initial.py`
- [X] T009 Create `features/sunday_school/dtos.py` (create/patch/order/theme requests, summary, lesson, year, index DTOs) with unit tests
- [X] T010 Create `features/sunday_school/repositories/{interfaces.py,year_repository.py,lesson_repository.py}` and register providers (`scripture_index`, repositories) in `config/di.py`; fakes in `features/sunday_school/tests/fakes.py`

## Phase 3: User Story 1 — Anyone reads this year's lessons (P1) 🎯 MVP

**Goal**: public index and lesson detail with ETag. **Independent test**: seed published lessons, GET index and lesson anonymously, 304 on repeat.

- [X] T011 [US1] Implement `features/sunday_school/services/reading_service.py` (published years, default year, index by year, published lesson + `books`) with unit tests on fakes in `features/sunday_school/tests/unit/test_reading_service.py`
- [X] T012 [US1] Implement public views `features/sunday_school/views/public.py`, OpenAPI serializers in `features/sunday_school/serializers.py`, `features/sunday_school/urls.py`, include in `config/urls.py`, wire module in `config/di.py`
- [X] T013 [US1] API tests in `features/sunday_school/tests/integration/test_public_api.py` (default year, `?year=`, drafts hidden, 404s, empty index, 304) (the ORM repositories are exercised through these API tests and `test_load_migration.py`)

## Phase 4: User Story 2 — Leadership writes and publishes a lesson (P1)

**Goal**: panel create/read/update with validation. **Independent test**: Liderança creates a draft, it is hidden publicly, publishes it, it appears.

- [X] T014 [US2] Implement `features/sunday_school/services/management_service.py` (list year, get, create, patch incl. year move, authors) with unit tests in `features/sunday_school/tests/unit/test_management_service.py`
- [X] T015 [US2] Panel views list/create/retrieve/patch in `features/sunday_school/views/manage.py` + routes + serializers
- [X] T016 [US2] API tests in `features/sunday_school/tests/integration/test_manage_api.py` (create, implicit year, content errors with path, bad reference, patch, move year, permissions 401/403)

## Phase 5: User Story 3 — Leadership orders the lessons of a year (P2)

- [X] T017 [US3] Add `set_order` to the management service and repository (exact id set, 0..n-1, transaction) with unit tests
- [X] T018 [US3] `PUT manage/lessons/order/` view + route + API tests (reorder, mismatch, unknown year, other year untouched)

## Phase 6: User Story 4 — Theme and delete (P3)

- [X] T019 [US4] Add delete (renumber) and year list/theme update to service and repositories with unit tests
- [X] T020 [US4] Views `DELETE manage/lessons/<id>/`, `GET manage/years/`, `PATCH manage/years/<year>/` + routes + API tests

## Phase 7: User Story 5 — This year's lessons arrive with the deploy (P1)

**Goal**: 18 lessons loaded by `migrate`. **Independent test**: migrate empty DB → 18 published lessons, 9 dates; rollback removes them.

- [X] T021 [US5] Convert the 18 source lessons (`C:\Users\gabri\Desktop\EBD PDF`) by hand into `features/sunday_school/migrations/data/2026/NN-<slug>.json` plus `year.json`, standard section icons, every Bible reference as `{printed, reference}`
- [X] T022 [US5] Write `features/sunday_school/migrations/0002_load_2026_lessons.py` (reason at top, forward + reverse)
- [X] T023 [US5] Tests: `features/sunday_school/tests/data/test_committed_lessons.py` (18 files, order, official dates only, schema, every reference in every translation, every section has an icon) and migration forward/backward test
- [ ] T024 [US5] **Stop for user review of the 18 lesson files before commit**

## Phase 8: Polish

- [X] T025 Run `pytest` (full suite) and `pre-commit run --all-files`; fix findings
- [X] T026 Check `specs/sunday-school/spec.md` and this feature's spec match the code (routes, errors, shapes)

## Dependencies

Setup → Foundational (T003–T010) → US1 → US2 → US3, US4 (independent of each other) ; US5 needs
T007–T008 only (schema + models) and can run in parallel with US1–US4.

## Parallel examples

- T004, T005, T006 touch different files.
- US5 conversion (T021) in parallel with US2–US4 code.

## Implementation strategy

MVP = Foundational + US1 + US5 (public reading of the imported lessons). US2–US4 add the panel.
