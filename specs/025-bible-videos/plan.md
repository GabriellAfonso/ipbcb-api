# Implementation Plan: Bible Videos and Reading Progress

**Branch**: `025-bible-videos` | **Date**: 2026-10-27 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/025-bible-videos/spec.md`

## Summary

`features/bible` gains its first models — `BibleVideo`, `BibleVideoPlace`,
`BibleChapterProgress`, `BibleVideoProgress` — and two services. `BibleVideoService` parses
YouTube links (pure), checks for a duplicate, reads title and thumbnail through a
`YouTubeMetadataClient` port (oEmbed over `requests`), and manages places and per-place order.
`BibleProgressService` folds a batch of offline changes with last-write-wins on `changed_at` and
writes the winners with one upsert per table. Books and chapters are validated against a
`BibleCanon` built from the loaded translations. `core` gains the scope `bible_videos` (Liderança
owner by data migration), a 503 base exception and the Bible exceptions.

## Technical Context

**Language/Version**: Python 3.14, `.venv_windows`

**Primary Dependencies**: Django 6.0, DRF 3.17, dependency-injector, Pydantic 2.12, `requests`
(already used). No new dependency.

**Storage**: PostgreSQL in production, SQLite in tests. Generated `bible/0001_initial`, generated
`core` `PanelScope` options migration, one hand-written data migration (scope level for
Liderança).

**Testing**: pytest + pytest-django; named fakes (`FakeYouTubeMetadataClient`,
`FakeBibleVideoRepository`, `FakeBibleProgressRepository`, `FixedClock`); mypy, ruff, bandit via
pre-commit.

**Target Platform**: Linux containers behind nginx; outbound HTTPS to `www.youtube.com` on save.

**Project Type**: Web service (REST API), single Android client.

**Performance Goals**: list in one query pair (videos + places); sync of 500 items in a fixed
number of queries (R-08).

**Constraints**: no queries in loops; ORM only in repositories; features never import each other;
files < 500 lines, functions 4–20 lines.

**Scale/Scope**: a few hundred videos; ≤ 1,189 chapter rows per user; 7 endpoints.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design; result unchanged.*

| Rule (`specs/constitution.md`, `CLAUDE.md`) | Status |
|---|---|
| Features never import each other | ✅ all in `features/bible`; user FK via `settings.AUTH_USER_MODEL` |
| Views → services → repositories; ORM only in repositories | ✅ |
| Services never import HTTP | ✅ oEmbed is a repository-layer port (R-04) |
| Wrap third-party libs | ✅ `requests` only in `HttpYouTubeOEmbedClient` |
| No queries in loops | ✅ grouped max, bulk upsert, bulk_update (R-07, R-08) |
| Input validated before DB | ✅ strict Pydantic DTOs; canon check on every book/chapter |
| `IsAuthenticated` on protected views; public explicitly marked | ✅ list `AllowAny` (FR-002), writes scope, progress `IsAuthenticated` |
| Domain exceptions with offending value | ✅ `core/domain/bible_exceptions.py` |
| Migrations generated; data migration documented | ✅ R-12 |
| Models: `__str__`, `Meta.ordering`, `verbose_name` | ✅ data-model |
| No hardcoded secrets | ✅ oEmbed needs no key |
| Spec before code, same commit | ✅ `specs/bible/spec.md`, `specs/012-…/spec.md` updated in the implementation commit |

Gate: **pass**.

## Technical Decisions

See [research.md](research.md): placement (R-01), `BibleCanon` (R-02), link parsing (R-03),
oEmbed port (R-04), 503 base (R-05), duplicate first (R-06), positions (R-07), sync fold and
upsert (R-08), per-item vs whole-batch validation (R-09), routes (R-10), ETag (R-11), scope and
migrations (R-12).

### Create flow

```
create(dto, creator):
  target = parse_youtube_link(dto.url)              # BibleVideoInvalidUrlError
  places = canon.normalise(dto.places)              # BiblePlaceInvalidError, ≥ 1, no repeats
  existing = repo.find_by_target(kind, youtube_id)  # → BibleVideoExistsError(video)
  meta = youtube.fetch(target)                      # Unavailable / LookupFailed
  return repo.create(target, meta, places, creator) # appends each place at max + 1
```

### Sync flow

```
sync(user, changes, now):
  verdicts = per item: canon/offset/future checks; video ids checked in one query
  stored   = repo.chapter_marks(user, targets), repo.video_marks(user, targets)
  winners  = fold accepted items in order: keep if no stored or changed_at > stored.changed_at
  repo.save_marks(user, winners)                     # one upsert per table, one transaction
```

### Implementation order

1. Specs: `specs/bible/spec.md` (videos, places, progress, endpoints, errors), `specs/012` (scope).
2. `core`: `Scope.BIBLE_VIDEOS`, migrations; `UpstreamUnavailableError` + 503; Bible exceptions;
   access matrix test.
3. `bible/domain`: `canon.py`, `youtube_links.py` + unit tests; `BibleRepository.canon()`.
4. Models + migration; DTOs.
5. Repositories (video, progress) + integration tests; oEmbed client + unit tests.
6. Services + unit tests with fakes.
7. Views, serializers (schema), URLs, DI + API integration tests.
8. Full suite, pre-commit.

## Project Structure

### Documentation (this feature)

```text
specs/025-bible-videos/
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
│   ├── domain/access.py                         # + BIBLE_VIDEOS
│   ├── domain/base_exceptions.py                # + UpstreamUnavailableError
│   ├── domain/bible_exceptions.py               # new
│   ├── domain/exceptions.py                     # re-exports
│   ├── http/exceptions.py                       # 503 mapping
│   ├── migrations/0011_*.py, 0012_*.py          # options (generated), Liderança owner (data)
│   └── tests/integration/test_management_access_matrix.py
├── features/bible/
│   ├── domain/{canon.py, youtube_links.py}
│   ├── models/{__init__.py, bible_video.py, bible_progress.py}
│   ├── migrations/0001_initial.py               # generated
│   ├── video_dtos.py, progress_dtos.py
│   ├── repositories/{__init__.py, bible_text.py, interfaces.py, video_repository.py,
│   │                 progress_repository.py, youtube_oembed.py}   # bible_text = today's file + canon()
│   ├── services/{__init__.py, bible_service.py, video_service.py, progress_service.py}
│   ├── serializers.py                           # OpenAPI schema only
│   ├── views/{__init__.py, videos.py, progress.py}
│   ├── urls.py
│   └── tests/{fakes.py, unit/…, integration/…}
└── config/di.py
```

**Structure Decision**: `repositories.py` and `services.py` become packages (`repositories/`,
`services/`) re-exporting today's names, so existing imports keep working.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Hand-written data migration | Levels live in role groups (spec 012) | Code cannot grant Liderança a level |
