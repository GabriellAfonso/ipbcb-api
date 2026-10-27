# Implementation Plan: Sunday School Lessons

**Branch**: `026-sunday-school` | **Date**: 2026-10-27 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/026-sunday-school/spec.md`

## Summary

A new feature `features/sunday_school` with two models (`SundaySchoolYear`,
`SundaySchoolLesson`), a strict Pydantic content schema of ten block types, a public read service
(index by year, lesson detail, `ETag`) and a panel service (CRUD, reorder, year theme) under the
new scope `sunday_school`. Bible references and `book_facts` are checked and enriched through a
`ScriptureIndex` built in DI from plain mappings the Bible repository exposes, so the feature
never imports `features.bible`. A data migration loads the 18 lessons of 2026 from frozen JSON
files converted by hand from the source PDFs/PPTX.

## Technical Context

**Language/Version**: Python 3.14, `.venv_windows`

**Primary Dependencies**: Django 6.0, DRF 3.17, dependency-injector, Pydantic 2.12. No new
dependency.

**Storage**: PostgreSQL in production, SQLite in tests. `JSONField` for content (both backends).
Generated `sunday_school/0001_initial`, generated `core/0013` (PanelScope options), hand-written
data migrations `core/0014` (Liderança owner) and `sunday_school/0002` (2026 lessons).

**Testing**: pytest + pytest-django; named fakes (`FakeLessonRepository`, `FakeYearRepository`);
`ScriptureIndex` built from a small in-memory outline in unit tests; committed-files test against
the real Bible data read by path. mypy, ruff, bandit via pre-commit.

**Target Platform**: Linux containers behind nginx.

**Project Type**: Web service (REST API), single Android client.

**Performance Goals**: index in 2 queries (published years, lessons of one year); lesson detail in
1 query (`select_related("year")`); reorder in a fixed number of queries.

**Constraints**: no queries in loops; ORM only in repositories; features never import each other;
files < 500 lines, functions 4–20 lines.

**Scale/Scope**: ~20–40 lessons a year; content < 100 KB per lesson; 10 endpoints.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design; result unchanged.*

| Rule (`specs/constitution.md`, `CLAUDE.md`) | Status |
|---|---|
| Features never import each other | ✅ `ScriptureIndex` from primitives wired in `config/di.py` (R-02) |
| Views → services → repositories; ORM only in repositories | ✅ |
| Services never import HTTP | ✅ user id passed as `UUID` |
| Management endpoint declares one scope | ✅ `sunday_school`, method defaults, no lowered override |
| Public endpoints explicitly marked | ✅ `AllowAny` only on the two public views (R-09) |
| Input validated before DB | ✅ strict DTOs + content schema + scripture check |
| Domain exceptions with offending value | ✅ `core/domain/sunday_school_exceptions.py` |
| Caching: caller-dependent responses private | ✅ panel GETs `private=True` (R-10) |
| Migrations generated; data migrations documented and reversible | ✅ R-08, R-11 |
| Models: `__str__`, `Meta.ordering`, `verbose_name` | ✅ data-model |
| Spec before code, same commit | ✅ `specs/sunday-school/spec.md` (domain), `specs/012-…` (scope) |

Gate: **pass**.

## Technical Decisions

See [research.md](research.md): placement (R-01), Bible boundary (R-02), `book_facts` numbers
(R-03), schema shape (R-04), content errors (R-05), icons and default section icons (R-06),
positions (R-07), initial load (R-08), routes (R-09), caching (R-10), scope (R-11), authors (R-12).

### Write flow

```
create(dto, user_id):
  content = validate_content(dto.content, scripture)   # SundaySchoolContentInvalidError
  return repo.create(dto, content, user_id)            # get_or_create year, position = max + 1

update(id, patch, user_id):
  lesson = repo.get(id) or LessonNotFound
  content = validate_content(...) if "content" in patch
  repo.update(id, changes, user_id)                    # year change: append there, renumber old
```

### Implementation order

1. Specs: `specs/sunday-school/spec.md` (domain), `specs/012` (scope list), this feature's spec
   contract synced with `contracts/api.md`.
2. `core`: `Scope.SUNDAY_SCHOOL`, migrations 0013/0014, exceptions, access matrix test.
3. Bible repository: `verse_counts_by_book()`, `book_names()` + tests.
4. `sunday_school/domain`: `icons.py`, `scripture_index.py`; `content_schema.py`; unit tests.
5. Models + `0001_initial`; DTOs.
6. Repositories + integration tests.
7. Services (public, panel, content validation) + unit tests with fakes.
8. Views, serializers (schema only), URLs, DI, settings + API integration tests.
9. Lesson files (18, converted by hand), `0002` data migration, committed-files test. **User
   reviews the files before commit.**
10. Full suite, pre-commit.

## Project Structure

### Documentation (this feature)

```text
specs/026-sunday-school/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/api.md
└── tasks.md
```

### Source Code

```text
server/
├── core/
│   ├── domain/access.py                         # + SUNDAY_SCHOOL
│   ├── domain/sunday_school_exceptions.py       # new
│   ├── domain/exceptions.py                     # re-exports
│   └── migrations/0013_*.py, 0014_*.py
├── features/bible/repositories/bible_text.py    # + verse_counts_by_book(), book_names()
├── features/sunday_school/
│   ├── apps.py, __init__.py
│   ├── domain/{icons.py, scripture_index.py}
│   ├── content_schema.py
│   ├── content_validation.py                    # schema + scripture checks → domain error
│   ├── dtos.py
│   ├── models/{__init__.py, year.py, lesson.py}
│   ├── migrations/{0001_initial.py, 0002_load_2026_lessons.py, data/2026/*.json}
│   ├── repositories/{__init__.py, interfaces.py, lesson_repository.py, year_repository.py}
│   ├── services/{__init__.py, reading_service.py, management_service.py}
│   ├── serializers.py                           # OpenAPI schema only
│   ├── views/{__init__.py, public.py, manage.py}
│   ├── urls.py
│   └── tests/{fakes.py, unit/…, integration/…, data/…}
├── config/di.py, config/urls.py, config/settings/base.py
```

**Structure Decision**: one new feature app; the only change in another feature is two read
methods on the Bible repository, consumed through DI.

## Complexity Tracking

| Item | Why | Simpler alternative rejected because |
|---|---|---|
| Migration imports `LessonContent` | User asked the import to validate through the same schema | A frozen copy of the schema in the migration would drift silently; the committed-files test guards the coupling |
