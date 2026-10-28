# Tasks: Doctrine Documents in the Database

**Input**: Design documents from `specs/027-doctrine-database/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/doctrine-api.md

**Tests**: required by the spec (FR-014) and by the project rules (every new function gets a test).

All paths are relative to `server/features/doctrine/` unless they start with `specs/` or `server/`.

## Phase 1: Setup

- [X] T001 Create `migrations/__init__.py` and move the three files from `data/` to `migrations/data/` with `git mv`, then rewrite them as compact UTF-8 JSON (`separators=(",", ":")`, `ensure_ascii=False`) without changing any value (research R-04)
- [X] T002 Point `DOCTRINE_DATA_DIR` at `migrations/data` and update the module docstring in `loading.py` (the files are now the migration's frozen input)

## Phase 2: Foundational (blocks every story)

- [X] T003 Add `edition: str | None = None` and `year: int | None = None` to `CatechismDocument`, `ConfessionDocument` and `DoctrineDocumentSummary` in `dtos.py` (research R-03)
- [X] T004 Create `DoctrineStandard` in `models.py` per data-model.md (`__str__`, `Meta.ordering = ["position"]`, `verbose_name`)
- [X] T005 Generate `migrations/0001_initial.py` with `python manage.py makemigrations doctrine` from `server/`
- [X] T006 Write the data migration `migrations/0002_load_westminster_standards.py`: reason at the top, `forward` loads with `load_doctrine_documents(DOCTRINE_DATA_DIR)` and `bulk_create`s rows (`content` = `questions`/`chapters` of `model_dump(mode="json", exclude_unset=True)`, `edition` "", `year` null), `backward` deletes the rows whose slugs the files hold (research R-04)

**Checkpoint**: `python manage.py migrate` on an empty database creates the three rows.

## Phase 3: User Story 1 — Read the doctrine documents exactly as before (P1) 🎯 MVP

**Goal**: the endpoints serve the table with the same bodies as before (plus `edition`/`year`).

**Independent Test**: on a migrated database, list and detail bodies equal the frozen files plus `edition`/`year` `null`; `ETag`/`304`; `404`.

- [X] T007 [US1] Rewrite `DoctrineRepositoryImpl` in `repositories.py` to read `DoctrineStandard` (ordered list; exact-slug get; `_to_document(row)` validates through the `DoctrineDocument` adapter, mapping `edition ""` to `None`) (research R-06)
- [X] T008 [US1] Carry `edition` and `year` from the document into the summary in `services.py`
- [X] T009 [P] [US1] Add `edition` (`allow_null`) and `year` (`allow_null`) to `CatechismDocumentSerializer`, `ConfessionDocumentSerializer` and `DoctrineDocumentSummarySerializer` in `serializers.py` (OpenAPI only)
- [X] T010 [US1] Create `tests/stored_documents.py`: `store_documents(documents)` replaces every `DoctrineStandard` row with the given DTOs (same dump as the migration) — test helper, ORM allowed in tests
- [X] T011 [US1] Rewrite `fixture_doctrine` in `tests/integration/conftest.py` to store the fixture files in the table (no DI override); `reload()` re-reads the private copy and stores it again
- [X] T012 [US1] Update `tests/integration/test_doctrine_api.py`: bodies include `"edition": None, "year": None`; detail equals the stored file plus those keys; mark DB access
- [X] T013 [P] [US1] Create `tests/integration/test_doctrine_repository.py`: position order, exact-case slug, omitted `lists`/`text_after` stay omitted, `null` references stay `null`, empty `edition` reads as `None`, empty table lists nothing
- [X] T014 [P] [US1] Update `tests/unit/test_doctrine_service.py` summaries to include `edition`/`year`

## Phase 4: User Story 2 — Load the documents on deploy (P1)

**Goal**: `migrate` fills the table; the load validates and can be reversed.

**Independent Test**: fresh test database holds the three documents equal to the frozen files; reverse removes them; forward restores them.

- [X] T015 [US2] Create `tests/integration/test_load_migration.py`: three rows in position order with `edition` "" and `year` null; each row's content equals the matching frozen file's `questions`/`chapters`; `backward` removes exactly those slugs and keeps another row; `forward` after `backward` restores three rows
- [X] T016 [P] [US2] Point `tests/data/test_committed_documents.py` at the migration data (via `DOCTRINE_DATA_DIR`), drop the "no files yet" skip, and add the check that the only proof texts with `reference: null` are Larger Catechism Q153 and Q163

## Phase 5: User Story 3 — Documents cannot be edited (P2)

**Independent Test**: no write method on the endpoints; no doctrine model in the admin.

- [X] T017 [US3] Add to `tests/integration/test_doctrine_api.py`: `PUT`/`PATCH`/`DELETE` on detail and `POST` on list return `405`; `admin.site.is_registered(DoctrineStandard)` is false

## Phase 6: User Story 4 — Optional edition and year (P3)

**Independent Test**: a row with `edition`/`year` set serves them in list and detail.

- [X] T018 [US4] Add to `tests/integration/test_doctrine_api.py` a test that sets `edition="Edição IPB"`, `year=1647` on a stored fixture row and gets both back in the list entry and the detail body

## Phase 7: Polish & Cross-Cutting

- [X] T019 Remove `DoctrineConfig.ready()` and `validate_doctrine_data()` from `apps.py`, delete `tests/unit/test_startup_validation.py` and the empty `data/` directory (research R-05)
- [X] T020 Update `specs/doctrine/spec.md`: Data Model (table + content shape), Adding a document (new data migration), endpoints (`edition`, `year`), rules 2, 6 and 7, Errors (no `ImproperlyConfigured`), feature history link to `027`
- [X] T021 Run `python -m pytest features/doctrine -q`, then the full suite and `pre-commit run --all-files` from `server/`; check the API still matches `specs/027-doctrine-database/contracts/doctrine-api.md`

## Dependencies

- Phase 1 → Phase 2 → US1 → (US2, US3, US4 in any order) → Polish.
- T005 needs T004; T006 needs T001–T005; T007 needs T004; T011 needs T010; T012–T014 need T007–T011.
- US2–US4 only add tests on top of US1's fixtures and the migration.

## Parallel Opportunities

- T009 alongside T007/T008.
- T013, T014 alongside T012 once T011 is done.
- T016 alongside T015.

## Implementation Strategy

MVP is Phases 1–3: the table exists, is loaded and is served exactly as before. US2–US4 add the
migration, read-only and new-field guarantees as tests; Polish removes the file-based startup path
and updates the domain spec in the same commit as the code.
