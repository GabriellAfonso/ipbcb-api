# Implementation Plan: Doctrine Documents in the Database

**Branch**: `027-doctrine-database` | **Date**: 2026-10-27 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/027-doctrine-database/spec.md`

## Summary

The doctrine feature gets its first model, `DoctrineStandard` (one row per document; the questions
or chapters as one `JSONField`, plus optional `edition` and `year`). A generated `0001_initial`
creates the table and a hand-written data migration `0002_load_westminster_standards` loads the
three Westminster Standards from JSON files frozen beside it, validated by the existing
`load_doctrine_documents()`. The repository reads the table instead of files; startup validation
and `features/doctrine/data/` go away. The API keeps its paths and bodies, adding `edition` and
`year` (both `null`). Nothing is editable: no write endpoint, no admin registration.

## Technical Context

**Language/Version**: Python 3.14, `.venv_windows`

**Primary Dependencies**: Django 6.0, DRF 3.17, dependency-injector, Pydantic 2.12. No new
dependency.

**Storage**: PostgreSQL in production, SQLite in tests. `JSONField` for `content` (both backends).
Generated `doctrine/0001_initial`; hand-written data migration `doctrine/0002_load_westminster_standards`.

**Testing**: pytest + pytest-django. Unit tests of `loading.py`, DTOs and service unchanged (named
fake `FakeDoctrineRepository`); integration tests on the real table for the repository, the load
migration and the API; committed-data tests on the frozen migration files with the Bible data read
by path. mypy, ruff, bandit via pre-commit.

**Target Platform**: Linux containers behind nginx; `migrate` runs before gunicorn in
`compose.prod.yml`.

**Project Type**: Web service (REST API), single Android client.

**Performance Goals**: list in 1 query (3 rows) + ~25 ms validation; detail in 1 query + < 20 ms
validation for the largest document (research R-06).

**Constraints**: ORM only in repositories; features never import each other; files < 500 lines,
functions 4–20 lines; applied migrations never edited.

**Scale/Scope**: 3 rows, ~420 KB of compact JSON; 2 public endpoints, unchanged.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design; result unchanged.*

| Rule (`specs/constitution.md`, `CLAUDE.md`) | Status |
|---|---|
| Features never import each other | ✅ Bible data still read by path, in tests only |
| Views → services → repositories; ORM only in repositories | ✅ ORM moves into `DoctrineRepositoryImpl`; test helpers write rows directly (tests only) |
| Public endpoints explicitly marked | ✅ `AllowAny`, unchanged |
| Input validated before DB | ✅ no user input; migration data validated by the strict DTOs |
| Domain exceptions with offending value | ✅ `DoctrineDocumentNotFoundError` unchanged; `DoctrineDataError` names file, field, value |
| Caching: public data not private | ✅ unchanged |
| Migrations generated; data migrations documented and reversible | ✅ `0001` generated, `0002` with reason at the top and a reverse (R-04) |
| Models: `__str__`, `Meta.ordering`, `verbose_name` | ✅ data-model |
| Spec before code, same commit | ✅ `specs/doctrine/spec.md` updated with the code |

Gate: **pass**.

## Technical Decisions

See [research.md](research.md): model name (R-01), content column (R-02), `edition`/`year` (R-03),
initial load (R-04), startup validation removed (R-05), reading and no cache (R-06), read-only
(R-07), tests (R-08).

### Read flow

```
list_documents():
  rows = DoctrineStandard.objects.order_by("position")      # 1 query
  return [_to_document(row) for row in rows]                # DTO validation
service: summaries with item_count, edition, year

get_document(slug):
  row = DoctrineStandard.objects.filter(slug=slug).first()  # exact match; SQLite/Postgres "=" is case-sensitive
  return _to_document(row) if row else None
```

### Load flow (migration 0002)

```
forward:  documents = load_doctrine_documents(DOCTRINE_DATA_DIR)   # DoctrineDataError stops migrate
          bulk_create(row per document, content = dump(exclude_unset)[questions|chapters])
backward: delete rows whose slug is in the frozen files
```

## Project Structure

### Documentation (this feature)

```text
specs/027-doctrine-database/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/doctrine-api.md
├── checklists/requirements.md
└── tasks.md
```

### Source Code

```text
server/features/doctrine/
├── apps.py                     # ready() and validate_doctrine_data() removed
├── dtos.py                     # + edition, year
├── loading.py                  # DOCTRINE_DATA_DIR → migrations/data
├── models.py                   # NEW DoctrineStandard
├── repositories.py             # reads the table
├── serializers.py              # + edition, year (OpenAPI only)
├── services.py                 # summary carries edition, year
├── migrations/
│   ├── __init__.py
│   ├── 0001_initial.py         # generated
│   ├── 0002_load_westminster_standards.py
│   └── data/                   # the three files, moved from data/, compact JSON
├── data/                       # REMOVED
└── tests/
    ├── stored_documents.py     # NEW test helper: replace table rows with given documents
    ├── data/test_committed_documents.py      # points at migrations/data; + null-reference check
    ├── integration/conftest.py               # fixture_doctrine stores fixtures in the table
    ├── integration/test_doctrine_api.py      # + edition/year, + admin check
    ├── integration/test_doctrine_repository.py   # NEW
    ├── integration/test_load_migration.py        # NEW
    └── unit/test_startup_validation.py       # REMOVED
specs/doctrine/spec.md          # Data Model, Adding a document, rules 6–7, Errors
```

**Structure Decision**: everything stays inside `features/doctrine`; `config/di.py` keeps
`DoctrineRepositoryImpl` as a Singleton (now stateless).

## Complexity Tracking

No violations.
