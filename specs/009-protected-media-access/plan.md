# Implementation Plan: Protected Media Access

**Branch**: `009-protected-media-access` | **Date**: 2026-09-25 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/009-protected-media-access/spec.md`

## Summary

Route `/ipbcb/media/<path>` through a DRF view instead of letting nginx serve it from disk.
The view authenticates (JWT, `IsAuthenticated`), asks `MediaAccessService.authorize` to
validate the path, pick the folder's audience, check the caller against it and locate the file,
then answers with an empty `200` carrying `X-Accel-Redirect: /ipbcb/protected-media/<path>`
so nginx streams the bytes. With `DEBUG=True` it returns the file itself. Responses are
`Cache-Control: private, no-cache`; nginx supplies `ETag`/`Last-Modified` and the `304`s. The
dev-only `static(MEDIA_URL)` route is removed. No model, migration, serializer or API response
changes.

## Technical Context

**Language/Version**: Python 3.14, `.venv_windows`

**Primary Dependencies**: Django 6, DRF, dependency-injector, Pydantic. No new dependency.

**Storage**: Filesystem only (`MEDIA_ROOT`, bind-mounted at `./server/media` in prod). No
database change.

**Testing**: pytest + DRF `APIClient`, `override_settings(MEDIA_ROOT=tmp_path, DEBUG=False)`,
named fake repository for service unit tests, mypy, ruff/black.

**Target Platform**: Linux container (gunicorn + uvicorn workers) behind nginx, prefix `/ipbcb/`.

**Project Type**: Web service (REST API), single Android client.

**Performance Goals**: The backend never reads file bytes in production; per-image cost is one
authenticated request returning an empty body. Unchanged images cost a `304`.

**Constraints**: Public media URLs unchanged. Deploy order backend → app → nginx, same day
(spec, Dependencies).

**Scale/Scope**: One church congregation; `media` throttle `3000/hour` per user.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design — result unchanged.*

| Rule (`specs/constitution.md`) | Status |
|---|---|
| Protected endpoints require JWT; `IsAuthenticated` on every authenticated view | ✅ view declares `IsAuthenticated` |
| Features never import each other | ✅ `features/media` imports only `core` (R-02) |
| `core/` holds only entities shared by 2+ features | ✅ only the generic `PermissionDeniedError` and the permission fix go to `core`; the service stays in the feature |
| Views never access repositories; services never import HTTP objects | ✅ view → service; service receives a `MediaViewer` DTO, not `request` (R-03) |
| Repositories are the only layer touching persistence | ✅ filesystem behind `MediaFileRepository` (R-05) |
| DI through `config/di.py`; DTOs are Pydantic | ✅ |
| Canonical error shape; exceptions matched by `isinstance` | ✅ new exceptions subclass `NotFoundError` / new `PermissionDeniedError`, mapped in `_DOMAIN_STATUS_MAP` (R-10) |
| Uploaded files validated by decoded content | n/a — no upload path touched. A pre-existing violation in the gallery upload was found (R-08), reported, not fixed here |
| **Caching: per-caller responses use `private, no-store` + `Vary: Authorization`** | ⚠️ **Deliberate deviation**, decided in spec clarification (FR-013): media uses `private, no-cache` without `Vary: Authorization`. Recorded as an exception in the constitution in this same feature (FR-021) — see Complexity Tracking |
| Base path `/ipbcb/`, never hardcode absolute URLs | ✅ route derived from `MEDIA_URL`/`FORCE_SCRIPT_NAME` (R-06); `PROTECTED_MEDIA_LOCATION` is a setting, and an nginx-internal URI, not a client URL |
| `DEBUG = False` in production | ✅ delivery mode follows `DEBUG`; production always takes the `X-Accel-Redirect` branch |

Gate: **pass**, with the one justified deviation below.

## Technical Decisions

Full reasoning, alternatives and evidence in [research.md](research.md). Summary:

- **D-1 Path-addressed route** (R-01). Traversal risk handled by segment validation,
  resolved-path containment, and nginx's `internal` alias confining any redirect to the media
  directory.
- **D-2 New `features/media/` package**, not an installed app (R-02).
- **D-3 One service call, spec order** (R-03): `authorize(requested_path, viewer)` does
  validate → rule → audience → locate, and logs once.
- **D-4 Reuse `IsMemberUser` and `IsAdminUser`** — no new permission class (user decision
  during planning; spec FR-008 amended). Harden both against a user with no `Profile` row,
  which today escapes as a 500 (R-03 addendum).
- **D-5 Validate, never normalize** (R-04; user decision, spec US5.2 amended).
- **D-6 Filesystem behind `MediaFileRepository`**, root injected via `providers.Callable`
  so `override_settings` applies (R-05).
- **D-7 Route prefix derived from `MEDIA_URL` minus `FORCE_SCRIPT_NAME`**, `re_path` with
  `.*` (R-06).
- **D-8 Response per mode** (R-07): empty body + percent-encoded `X-Accel-Redirect` in prod,
  `FileResponse` in dev; `Cache-Control: private, no-cache` in both; no validators from Django.
- **D-9 `Content-Type` from a four-format allow-list**, else `application/octet-stream`
  (R-08).
- **D-10 One structured log line per decision**, folder only when it is a ruled folder
  (R-09).
- **D-11 Domain exceptions** incl. a new generic `PermissionDeniedError` → 403 (R-10).
- **D-12 `ScopedRateThrottle`, scope `media`** (R-11).

## Implementation Order

Each step leaves the tree consistent for the mypy pre-commit hook (it checks the whole tree).

1. **Spec and constitution first** (CLAUDE.md §6.2): constitution Caching exception + media
   rule + register-oracle wording (FR-021); `specs/gallery/spec.md` and
   `specs/accounts/spec.md` note on authenticated media URLs (FR-022).
2. **`core`**: `PermissionDeniedError` + media exceptions; `_DOMAIN_STATUS_MAP` entry for 403;
   harden `IsMemberUser`/`IsAdminUser`. Tests: handler maps `PermissionDeniedError` to 403 with
   `PERMISSION_DENIED`; permissions return `False` for a user without a profile.
3. **`features/media` domain + service**: `MediaAudience`, folder rules, `MediaViewer`,
   `MediaFile`, path validation, content-type table, `MediaAccessService.authorize` +
   `open`, decision log. Unit tests with `FakeMediaFileRepository`: every validation rule
   (parametrized over the spec's traversal forms), rule selection incl. look-alikes, audience
   matrix, order (403 before existence), log fields.
4. **Repository**: `MediaFileRepository` Protocol + `FileSystemMediaRepository`. Tests on
   `tmp_path`: existing file, missing file, directory, symlink escaping root (skipped when the
   OS refuses symlinks).
5. **View, URL, DI, settings**: `MediaFileAPIView` (`IsAuthenticated`, `ScopedRateThrottle`,
   `http_method_names = ["get", "head"]`), `features/media/urls.py` with the derived prefix,
   mount in `config/urls.py`, **remove** the `static(settings.MEDIA_URL, ...)` line, register
   repository + service and wire the view module in `config/di.py`,
   `PROTECTED_MEDIA_LOCATION` and the `media` throttle rate in `base.py`, `media` rate in
   `test.py`. Integration tests: the full SC-006 list, plus HEAD, 405, query string ignored,
   non-ASCII filename percent-encoded in the redirect, no `ETag`/`Last-Modified` on the
   redirect response, `Content-Type` allow-list, dev mode body.
6. **Housekeeping**: rewrite the comment in `ProfileRepositoryImpl.save_photo` (FR-020) to
   describe authenticated delivery and point to this spec.
7. **Validation**: quickstart §1–§2 locally; §4–§5 after the coordinated deploy.

## Project Structure

### Documentation (this feature)

```text
specs/009-protected-media-access/
├── spec.md
├── plan.md                      # this file
├── research.md                  # R-01 … R-12
├── data-model.md                # in-memory types, rules, exceptions
├── quickstart.md                # validation guide
├── contracts/media-endpoint.md  # public + nginx-internal contract
├── checklists/requirements.md
└── tasks.md                     # /speckit-tasks
```

### Source Code

```text
server/
├── config/
│   ├── di.py                          # + media_file_repository, media_access_service, wiring
│   ├── urls.py                        # + media urls; − static(MEDIA_URL)
│   └── settings/
│       ├── base.py                    # + PROTECTED_MEDIA_LOCATION, "media" throttle rate
│       └── test.py                    # + "media" test rate
├── core/
│   ├── domain/exceptions.py           # + PermissionDeniedError, Media*Error
│   ├── http/exceptions.py             # + 403 in _DOMAIN_STATUS_MAP
│   ├── http/permissions.py            # profile-less user → False, not 500
│   └── tests/unit/test_exception_handler.py   # + 403 mapping
├── features/
│   ├── accounts/
│   │   ├── repositories/profile_repository.py # comment only (FR-020)
│   │   └── tests/unit/test_permissions.py     # + no-profile regression
│   └── media/                         # new, not in INSTALLED_APPS
│       ├── __init__.py
│       ├── urls.py
│       ├── dtos/media_dtos.py         # MediaViewer, MediaFile
│       ├── domain/media_rules.py      # MediaAudience, folder rules, path validation, content types
│       ├── repositories/
│       │   ├── interfaces.py          # MediaFileRepository (Protocol)
│       │   └── filesystem_media_repository.py
│       ├── services/media_access_service.py
│       ├── views/media_file.py
│       └── tests/
│           ├── fakes.py               # FakeMediaFileRepository
│           ├── unit/test_media_rules.py
│           ├── unit/test_media_access_service.py
│           ├── unit/test_filesystem_media_repository.py
│           └── integration/test_media_file_api.py
specs/
├── constitution.md                    # Caching exception, media rule, register-oracle wording
├── gallery/spec.md                    # FR-022
└── accounts/spec.md                   # FR-022
```

**Structure Decision**: Same layered layout as every feature (`views → services →
repositories`, DTOs, per-feature tests). `domain/` holds the pure rule table and validation so
the service file stays under the size limits in CLAUDE.md §8.

## Out of scope, found during planning (reported, not changed)

- **Gallery uploads keep the original filename extension** (`GalleryRepositoryImpl.create_photo`),
  contradicting the constitution's "stored extension derived from detected format". Neutralized
  for delivery by D-9, but the stored names stay wrong.
- **DRF throttle counters are per worker** (no `CACHES` backend) — pre-existing, applies to
  every scope (R-11).

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Media responses use `private, no-cache` without `Vary: Authorization`, against the constitution's `private, no-store` + `Vary: Authorization` rule | Lets the phone keep images on disk and revalidate with `304`, while still checking permission on every view (immediate revocation) | `no-store` forces a full re-download of every image on every view. `Vary: Authorization` adds nothing: `private` already keeps the response out of shared caches, and a token refresh would needlessly invalidate the device cache. Recorded in the constitution as a named exception (FR-021) |
