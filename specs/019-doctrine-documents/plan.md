# Implementation Plan: Doctrine Documents (Westminster Standards)

**Branch**: `019-doctrine-documents` | **Date**: 2026-10-20 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/019-doctrine-documents/spec.md`

## Summary

A new read-only feature `features/doctrine`, same shape as `features/bible`: one JSON file per
document in `features/doctrine/data/`, committed as the source of truth (produced outside the
repository from the IPB PDFs and reviewed by a person; corrections are direct edits). Files are
validated with Pydantic at startup — `DoctrineConfig.ready()` refuses to boot on a bad file — and
served whole by two public endpoints with the project's ETag/304 helper.

Tests on the committed files guard what startup deliberately doesn't: the 107 / 196 / 33 counts,
and that every structured Bible reference uses a Bible-domain book abbreviation and points to a
chapter/verse existing in every served Bible version.

No ingestion command, script, PDF dependency or generated report is part of this feature.

## Technical Context

**Language/Version**: Python 3.14 (Dockerfile), Django 6.0.8

**Primary Dependencies**: DRF 3.17.2, Pydantic 2.12.5, `dependency-injector` 4.48.3, drf-spectacular 0.29.0. No new dependency

**Storage**: static JSON files in the repo, loaded into memory at startup. No database, no migration

**Testing**: pytest + pytest-django from `server/`; unit tests on fixture files in a temp dir; data tests on the real committed files; API integration tests

**Target Platform**: Linux container behind nginx at `/ipbcb/`

**Project Type**: web service (REST API for the Android app)

**Performance Goals**: no DB query; one in-memory lookup plus JSON serialisation and SHA-256 per request (few ms for ~300 KB)

**Constraints**: never serve a partial set; functions 4–20 lines; files under 500 lines

**Scale/Scope**: 3 documents, 303 questions, 33 chapters (~300 paragraphs), roughly 1–2k proof texts

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Rule | How this plan complies |
|------|------------------------|
| No endpoint bypasses auth unless explicitly marked public | Both views `AllowAny`, declared public in spec FR-015 and in `specs/doctrine/spec.md`, as Bible |
| Input validated before reaching storage | Only input is the `slug` path param; looked up in a dict, never used as a path |
| ORM only / no queries in loops | No database |
| Features never import each other | The reference test reads Bible data **files by path** (R-04); no `features.bible` import |
| Views → Services → Repositories | `DoctrineListView`/`DoctrineDetailView` → `DoctrineService` → `DoctrineRepositoryImpl` (only file I/O, via `loading.py`) |
| Services never import HTTP objects | Service returns DTOs, raises `DoctrineDocumentNotFoundError` |
| DI via `config/di.py`; DTOs not dicts | `doctrine_repository` Singleton, `doctrine_service` Factory; Pydantic DTOs throughout |
| Domain errors in `core/domain/exceptions.py` | `DoctrineDocumentNotFoundError(NotFoundError)` → canonical `404` |
| No hardcoded absolute URLs | Relative routes under the existing `include` |
| Code in English; user-facing text pt-BR | Code/slugs English; document text pt-BR as published |
| Specs and code in the same commit | `specs/doctrine/spec.md` + `docs/features/doctrine.md` written with the code |

**Gate**: PASS. Re-checked after Phase 1: PASS, no violations.

## Project Structure

### Documentation (this feature)

```text
specs/019-doctrine-documents/
├── plan.md              # this file
├── research.md          # resolved decisions, R-01 … R-07
├── data-model.md        # file format, DTOs, startup vs test rules, exceptions
├── quickstart.md        # how to validate
├── contracts/
│   └── doctrine-api.md
├── checklists/
│   └── requirements.md
└── tasks.md             # /speckit-tasks
```

### Source Code

```text
server/
├── config/
│   ├── settings/base.py                     # + "features.doctrine" in INSTALLED_APPS
│   ├── urls.py                              # + include("features.doctrine.urls")
│   └── di.py                                # + doctrine_repository (Singleton), doctrine_service; wire views
├── core/domain/exceptions.py                # + DoctrineDocumentNotFoundError
└── features/doctrine/
    ├── apps.py                              # DoctrineConfig.ready(): load + validate, ImproperlyConfigured
    ├── data/                                # westminster-*.json × 3 (committed, source of truth)
    ├── dtos.py                              # served DTOs (data-model.md)
    ├── loading.py                           # read dir → validated documents; cross-file rules; DoctrineDataError
    ├── repositories.py                      # DoctrineRepository protocol + Impl (uses loading.py)
    ├── services.py                          # list_documents(), get_document(slug)
    ├── serializers.py                       # OpenAPI-only response serializers (R-07)
    ├── views/__init__.py                    # DoctrineListView, DoctrineDetailView (+ ETag helper)
    ├── urls.py
    └── tests/
        ├── fakes.py                         # FakeDoctrineRepository
        ├── fixtures/                        # small valid documents + one file per broken rule
        ├── bible_verse_index.py             # test-only: Bible JSON files → min verse counts (R-04)
        ├── unit/                            # DTO rules, loading rules, service
        ├── data/test_committed_documents.py # counts, Confession 1.2 shape, book abbrevs, verse existence
        └── integration/test_doctrine_api.py # list order/counts, detail, 404, ETag/304, ready() guard

docs/features/doctrine.md                    # feature doc, like docs/features/bible.md
specs/doctrine/spec.md                       # domain spec (CLAUDE.md §6), current state
```

**Structure Decision**: one new feature app mirroring `features/bible`. Changes outside it are
registration only (settings, urls, di) and the one domain exception. The data test is the only code
that reads another feature's files, by path, and only in tests.

## Implementation Order

1. **Served side on fixtures**: DTOs, `loading.py` with every startup rule, repository, service,
   exception, views, URLs, DI, `ready()`. Unit and integration tests run against small fixture
   files. Proves the contract before the real data exists.
2. **Data tests**: `bible_verse_index.py` and `test_committed_documents.py`, written against the
   rules in data-model.md. They fail until the real files are in place.
3. **Real data**: add the three JSON files produced outside the repository and reviewed by a
   person. Fix any data-test failure in the JSON (human decision), never by loosening the test.
4. **Docs**: `specs/doctrine/spec.md`, `docs/features/doctrine.md`, in the same commit as the code
   they describe (CLAUDE.md §6.2).

Each commit must leave the tree consistent for the mypy hook and the test run: since `ready()`
validates `data/`, step 3's files must be valid when committed, and step 2's data tests must not
be committed red — commit them together with step 3 (or mark the data-dependent tests to skip
while `data/` is empty, and remove the skip in step 3).

## Complexity Tracking

No constitution violation to justify.
