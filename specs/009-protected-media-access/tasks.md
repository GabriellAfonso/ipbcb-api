---

description: "Task list for 009 Protected Media Access"
---

# Tasks: Protected Media Access

**Input**: Design documents from `specs/009-protected-media-access/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/media-endpoint.md, quickstart.md

**Tests**: Required. The spec lists the mandatory cases (SC-006) and CLAUDE.md §10 requires a
test for every new function and a regression test for every bug fix. Test tasks come before
the implementation they cover inside each phase; write them first and watch them fail.

**Organization**: Tasks grouped by user story. The whole feature ships in **one** backend
deploy (spec, Dependencies), so "independent" here means each story's behaviour is
implemented and proven by its own tests, not deployed alone.

**Paths**: Python source lives under `server/`. Commands run from `server/` with
`..\.venv_windows\Scripts\python`. The mypy pre-commit hook checks the whole tree, so every
commit must leave it consistent (memory: commit-splitting constraint).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1–US6 from spec.md

---

## Phase 1: Setup (spec first, then skeleton)

**Purpose**: CLAUDE.md §6.2 — specs change before code, in the same commit series.

- [X] T001 Update `specs/constitution.md`: (a) under Security → Caching, add a named media exception — media responses use `Cache-Control: private, no-cache` without `Vary: Authorization`, validators (`ETag`/`Last-Modified`) and `304` come from nginx, the backend sets none on the redirect response, reason: `no-store` would re-download every image and `no-cache` keeps revocation immediate (link `specs/009-protected-media-access/plan.md` Complexity Tracking); (b) add a Security bullet "Media is served only through the authenticated access check (`features/media`), default deny by first path segment; nginx serves `MEDIA_ROOT` only through the `internal` `/ipbcb/protected-media/` location — its only record in this project, like the metrics block"; (c) in the register-oracle accepted-risk bullet, add that the photo-URL leak is now also closed by authenticated media delivery. Leave the OpenAPI accepted risk unchanged.
- [X] T002 [P] In `specs/gallery/spec.md`, state that the `image` URL returned by the photo endpoints is readable only by members through the media access check (`/ipbcb/media/gallery/...`, see `specs/009-protected-media-access/spec.md`) (FR-022).
- [X] T003 [P] In `specs/accounts/spec.md`, state that `photo_url` is readable only by members through the media access check (`/ipbcb/media/profiles/...`) (FR-022).
- [X] T004 Create the package skeleton `server/features/media/` with empty `__init__.py` in `features/media/`, `dtos/`, `domain/`, `repositories/`, `services/`, `views/`, `tests/`, `tests/unit/`, `tests/integration/`. Do **not** add it to `INSTALLED_APPS` (research R-02).

---

## Phase 2: Foundational (blocking prerequisites)

**Purpose**: Exceptions, permissions, types, rules, validation, repository and service that
every story's HTTP behaviour depends on.

**⚠️ CRITICAL**: No story work starts until this phase is complete. Path validation lives
here, not in US5, because no code path may produce an `X-Accel-Redirect` before it exists;
US5 owns the adversarial test matrix against it.

- [X] T005 [P] Test in `server/core/tests/unit/test_exception_handler.py`: a `PermissionDeniedError` goes through `custom_exception_handler` as `403` with `error_code == "PERMISSION_DENIED"`; `MediaAccessDeniedError` also maps to `403`; `MediaPathRejectedError`, `MediaFolderNotRuledError` and `MediaFileNotFoundError` built with the same path produce byte-identical `404` bodies with `error_code == "NOT_FOUND"`.
- [X] T006 [P] Regression test in `server/features/accounts/tests/unit/test_permissions.py`: for a user whose `Profile` row was deleted (`user.profile.delete()`, then refetch the user), `IsMemberUser().has_permission` and `IsAdminUser().has_permission` return `False` instead of raising `RelatedObjectDoesNotExist` (research R-03 addendum).
- [X] T007 Add to `server/core/domain/exceptions.py`: `PermissionDeniedError(DomainError)` with `error_code = "PERMISSION_DENIED"`; `MediaAccessDeniedError(PermissionDeniedError)`; `MediaPathRejectedError`, `MediaFolderNotRuledError`, `MediaFileNotFoundError` subclassing `NotFoundError`. The three 404 classes take the requested path and share one message template, `f"Arquivo não encontrado: {requested_path!r}"`, via a small shared base or helper so the text cannot drift (data-model.md, research R-10). Docstrings with a usage example.
- [X] T008 Map `PermissionDeniedError` to `status.HTTP_403_FORBIDDEN` in `_DOMAIN_STATUS_MAP` in `server/core/http/exceptions.py` (depends on T007). T005 passes.
- [X] T009 [P] In `server/core/http/permissions.py`, change both classes to `getattr(getattr(request.user, "profile", None), "is_member"/"is_admin", False)` so the profile lookup happens inside a defaulted `getattr`; add a one-line WHY comment (`RelatedObjectDoesNotExist` subclasses `AttributeError`). T006 passes.
- [X] T010 [P] Create `server/features/media/dtos/media_dtos.py`: `MediaViewer(StrictBaseModel)` with `is_member: bool`, `is_leader: bool`; `MediaFile(StrictBaseModel)` with `relative_path: str`, `absolute_path: Path`, `content_type: str` (data-model.md).
- [X] T011 [P] Unit tests in `server/features/media/tests/unit/test_media_rules.py` for the rules module: `audience_for_folder("gallery")` and `("profiles")` → `MEMBER`; unknown folder → `None`; `content_type_for("a/b/x.JPG")` → `image/jpeg`, `.jpeg`, `.png`, `.webp`, `.gif` mapped, `.html`/`.svg`/no extension → `application/octet-stream`; `validate_media_path` accepts `gallery/retiro-2025/IMG_0042.jpg` and `profiles/ana.paula/6f1c2d.png` and returns them unchanged; returns the first segment through `first_segment()`. (Adversarial rejection cases are US5, T028.)
- [X] T012 Create `server/features/media/domain/media_rules.py` (makes T011 pass): `MediaAudience` enum (`MEMBER`, `LEADER`); `MediaAccessOutcome` enum (`allowed`, `forbidden`, `not_found`, `rejected`, `unruled`); `FOLDER_RULES: Mapping[str, MediaAudience]` with `gallery` and `profiles` → `MEMBER` only (`members` is added in US3, T035); `audience_for_folder(folder) -> MediaAudience | None` (exact, case-sensitive); `validate_media_path(requested_path) -> str` raising `MediaPathRejectedError` for every rule in research R-04 (empty, leading `/`, fewer than two segments, empty/`.`/`..` segment, `\`, `%`, `\x00`, chars `< 0x20` or `0x7f`) and never rewriting the input; `first_segment(path)`; `content_type_for(path)` with the four-format allow-list (research R-08). Each function 4–20 lines; docstrings with example.
- [X] T013 [P] Create `server/features/media/repositories/interfaces.py`: `MediaFileRepository(Protocol)` with `locate(relative_path: str) -> Path | None` and `open(path: Path) -> BinaryIO` (research R-05).
- [X] T014 [P] Unit tests in `server/features/media/tests/unit/test_filesystem_media_repository.py` on `tmp_path`: existing regular file → resolved `Path`; missing file → `None`; path naming a directory → `None`; `open` returns a readable binary handle with the file's bytes. (Symlink escape is US5, T030.)
- [X] T015 Create `server/features/media/repositories/filesystem_media_repository.py`: `FileSystemMediaRepository(root: Path)`; `locate` resolves root and `root / relative_path` with `resolve(strict=True)`, returns `None` on `FileNotFoundError`/`OSError`, when not `is_relative_to(resolved_root)`, or when not `is_file()`; `open` returns `path.open("rb")`. T014 passes.
- [X] T016 [P] Create `server/features/media/tests/fakes.py`: `FakeMediaFileRepository` holding a `dict[str, bytes]` of relative paths → contents; `locate` returns a fake `Path` for known keys, else `None`; records every `locate` call so tests can assert it was **not** called (order checks).
- [X] T017 Unit tests in `server/features/media/tests/unit/test_media_access_service.py` for the decision sequence with `FakeMediaFileRepository` (depends on T016): member viewer + existing `gallery/...` file → `MediaFile` with verbatim `relative_path` and the allow-listed `content_type`; non-member viewer on `gallery/` → `MediaAccessDeniedError` **and** `locate` never called; member on missing file → `MediaFileNotFoundError`; unknown folder `reports/x.pdf` → `MediaFolderNotRuledError` even for a viewer with both flags; each outcome emits exactly one `media_access` log record (use `caplog`) with `folder` and `outcome` fields, and no record contains the file part of the path.
- [X] T018 Create `server/features/media/services/media_access_service.py`: `MediaAccessService(repository: MediaFileRepository)` with `authorize(requested_path: str, viewer: MediaViewer) -> MediaFile` implementing data-model.md's sequence (validate → rule → audience → locate), and `open(media_file) -> BinaryIO` delegating to the repository. One private `_log_decision(folder, outcome)` writing `logger.info("media_access", extra={"folder": ..., "outcome": ...})`, where `folder` is the first segment only when it is a key of `FOLDER_RULES`, else `None` (research R-09). Methods 4–20 lines, early returns. T017 passes.
- [X] T019 Register in `server/config/di.py`: `media_file_repository = providers.Factory(FileSystemMediaRepository, root=providers.Callable(_media_root))` where `_media_root()` returns `Path(settings.MEDIA_ROOT)` at call time (so `override_settings` applies, research R-05); `media_access_service = providers.Factory(MediaAccessService, repository=media_file_repository)`; add `"features.media.views.media_file"` to `wiring_config.modules`.
- [X] T020 [P] Settings: in `server/config/settings/base.py` add `PROTECTED_MEDIA_LOCATION = "/ipbcb/protected-media/"` beside `MEDIA_URL` with a comment that it is the nginx-internal location, not a client URL, and `"media": "3000/hour"` to `DEFAULT_THROTTLE_RATES` with a comment (own scope so images never spend the API quota; revalidations count, spec FR-017); in `server/config/settings/test.py` add `"media": "99999/min"` with the same explanation as `hymnal_ingest`.

**Checkpoint**: `pytest features/media core/tests features/accounts/tests/unit/test_permissions.py` and `mypy .` green. No route exists yet.

---

## Phase 3: User Story 1 — A leaked media URL is useless without an account (P1) 🎯 MVP

**Goal**: Every `/ipbcb/media/...` request reaches the access check, and anonymous callers
get `401` before the path is examined.

**Independent Test**: With a real file under `gallery/`, an anonymous `GET` of its media URL
returns `401` and no file content or redirect header.

- [X] T021 [P] [US1] Integration tests in `server/features/media/tests/integration/test_media_file_api.py` (`override_settings(MEDIA_ROOT=tmp_path)`, file written to `tmp_path/gallery/retiro-2025/IMG_0042.jpg`): anonymous `GET /ipbcb/media/gallery/retiro-2025/IMG_0042.jpg` → `401` with `error_code == "NOT_AUTHENTICATED"`, empty of `X-Accel-Redirect`, body not the file bytes; malformed and expired `Bearer` token → `401` `AUTHENTICATION_FAILED`; anonymous request for a missing path → `401` (not `404`); anonymous `/ipbcb/media/` (empty path) → `401` in the canonical shape; member `POST` → `405`.
- [X] T022 [US1] Create `server/features/media/views/media_file.py`: `MediaFileAPIView(APIView)` with `permission_classes = [IsAuthenticated]`, `throttle_classes = [ScopedRateThrottle]`, `throttle_scope = "media"`, `http_method_names = ["get", "head"]`; `get(request, requested_path, media_access_service = Provide[Container.media_access_service])` builds `MediaViewer` from `IsMemberUser().has_permission(request, self)` / `IsAdminUser().has_permission(request, self)`, calls `authorize`, and passes the `MediaFile` to a response builder (T027). Keep the view to HTTP concerns only (spec FR-018).
- [X] T023 [US1] Create `server/features/media/urls.py`: `media_route_prefix()` returning `MEDIA_URL` minus `FORCE_SCRIPT_NAME` (when set) with the leading `/` stripped (prod `media/`, dev/test `ipbcb/media/`, research R-06; docstring with both examples); `urlpatterns = [re_path(rf"^{re.escape(prefix)}(?P<requested_path>.*)$", MediaFileAPIView.as_view(), name="media-file")]`.
- [X] T024 [US1] In `server/config/urls.py`, add `path("", include("features.media.urls"))` and **remove** `urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)`; keep the `STATIC_URL` line. T021 passes.
- [X] T025 [P] [US1] Unit test in `server/features/media/tests/unit/test_media_route_prefix.py`: `media_route_prefix()` is `"media/"` under `override_settings(FORCE_SCRIPT_NAME="/ipbcb", MEDIA_URL="/ipbcb/media/")` and `"ipbcb/media/"` with `FORCE_SCRIPT_NAME=None`.

**Checkpoint**: Media is no longer reachable anonymously through Django in any mode.

---

## Phase 4: User Story 2 — Members keep seeing gallery and profile photos (P1) 🎯 MVP

**Goal**: Members get the production internal redirect with the right headers; non-members
get `403`; missing files `404`.

**Independent Test**: As a member, request a gallery file and another member's profile photo
under `DEBUG=False`; each returns `200`, empty body, `X-Accel-Redirect` to
`/ipbcb/protected-media/<path>`, `Cache-Control: private, no-cache`.

- [X] T026 [P] [US2] Integration tests in `server/features/media/tests/integration/test_media_file_api.py` under `@override_settings(DEBUG=False, MEDIA_ROOT=tmp_path)`: member on `gallery/retiro-2025/IMG_0042.jpg` → `200`, `response.content == b""`, `X-Accel-Redirect == "/ipbcb/protected-media/gallery/retiro-2025/IMG_0042.jpg"`, `Cache-Control == "private, no-cache"`, `Content-Type == "image/jpeg"`, no `ETag`, no `Last-Modified`, `Vary` does not contain `Authorization`; member on another user's `profiles/ana.paula/<hex>.png` → same shape, `image/png`; non-member (`make_user`) on both → `403` `PERMISSION_DENIED`; member on `gallery/retiro-2025/missing.jpg` → `404` `NOT_FOUND`; `HEAD` as member → `200` with the same `X-Accel-Redirect`; query string `?v=2` → redirect path has no `?v=2`.
- [X] T027 [US2] Add the response builder to `server/features/media/views/media_file.py`: `_accel_redirect_response(media_file)` returning `HttpResponse(b"")` with `X-Accel-Redirect = quote(settings.PROTECTED_MEDIA_LOCATION + media_file.relative_path, safe="/")`, `Content-Type = media_file.content_type`, `Cache-Control = "private, no-cache"` (research R-07); the view returns it when `settings.DEBUG` is false. T026 passes.

**Checkpoint**: US1 + US2 is the behaviour the app needs; together with US5 it is the minimum
that can be deployed.

---

## Phase 5: User Story 5 — Path tricks never escape the media folder (P1) 🎯 MVP

**Goal**: Every traversal and encoding trick is rejected with `404` and never produces a
redirect; containment holds on the resolved file.

**Independent Test**: Send each traversal form as a member; no response carries
`X-Accel-Redirect` or file bytes.

- [X] T028 [P] [US5] Parametrized unit tests in `server/features/media/tests/unit/test_media_rules.py`: `validate_media_path` raises `MediaPathRejectedError` for `""`, `"/etc/passwd"`, `"gallery"`, `"gallery/"`, `"gallery//x.jpg"`, `"gallery/./x.jpg"`, `"gallery/../members/x.jpg"`, `"gallery/../../config/settings/base.py"`, `"../x"`, `"gallery\\..\\..\\x"`, `"gallery/%2e%2e/x"`, `"gallery/x%00.jpg"`, `"gallery/x\x00.jpg"`, `"gallery/x\n.jpg"`, `"gallery/x\x7f.jpg"`.
- [X] T029 [P] [US5] Integration tests in `server/features/media/tests/integration/test_media_traversal_api.py` under `DEBUG=False`, as a member, with a sentinel file placed **outside** `MEDIA_ROOT` (sibling of `tmp_path/media`) and `MEDIA_ROOT=tmp_path/media`: requests to `/ipbcb/media/gallery/../../sentinel.txt`, `gallery/%2e%2e/%2e%2e/sentinel.txt`, `gallery/..%2f..%2fsentinel.txt`, `gallery/%252e%252e/sentinel.txt`, `/ipbcb/media//etc/passwd`, `gallery/../gallery/x.jpg` each return `404` and none has an `X-Accel-Redirect` header or the sentinel's bytes. Use `client.get(path)` with the raw string so the test client does not normalize it; assert on `response.status_code` and `"X-Accel-Redirect" not in response`.
- [X] T030 [P] [US5] Symlink test in `server/features/media/tests/unit/test_filesystem_media_repository.py`: a symlink at `tmp_path/media/gallery/a/link.jpg` pointing at a file outside `tmp_path/media` → `locate` returns `None`; skip with `pytest.skip` when `os.symlink` raises `OSError` (Windows without developer mode, research R-12).
- [X] T031 [P] [US5] Integration test in `server/features/media/tests/integration/test_media_file_api.py`: a member requesting `gallery/ceia-de-natal/Ceia_ção.jpg` (file present) gets `X-Accel-Redirect == "/ipbcb/protected-media/gallery/ceia-de-natal/Ceia_%C3%A7%C3%A3o.jpg"` — ASCII-only, percent-encoded, `/` kept (research R-07).
- [X] T032 [US5] Fix whatever T028–T031 expose in `server/features/media/domain/media_rules.py` or `server/features/media/repositories/filesystem_media_repository.py`; every test in this phase green.

**Checkpoint**: MVP complete — US1, US2, US5 green. Safe to deploy the backend (step 1 of the
spec's deploy order).

---

## Phase 6: User Story 3 — Leader-only photos reserved before they exist (P2)

**Goal**: `members/` is readable by leaders only.

**Independent Test**: A file under `members/` returns `403` to a plain member and `200` with
redirect to a leader.

- [X] T033 [P] [US3] Unit tests in `server/features/media/tests/unit/test_media_access_service.py`: `members/x.jpg` with viewer `(is_member=True, is_leader=False)` → `MediaAccessDeniedError` and `locate` not called; `(False, True)` → `MediaFile`; `(True, True)` → `MediaFile`; `(False, False)` → denied. And in `test_media_rules.py`: `audience_for_folder("members")` → `LEADER`.
- [X] T034 [P] [US3] Integration tests in `server/features/media/tests/integration/test_media_file_api.py` under `DEBUG=False`: plain member on existing `members/x.jpg` → `403`; plain member on **missing** `members/nope.jpg` → `403` (existence not observable); `make_admin_client()` (leader, not member) on existing file → `200` with `X-Accel-Redirect: /ipbcb/protected-media/members/x.jpg`.
- [X] T035 [US3] Add `"members": MediaAudience.LEADER` to `FOLDER_RULES` in `server/features/media/domain/media_rules.py` with a comment that it is reserved for the upcoming members feature. T033–T034 pass.

---

## Phase 7: User Story 4 — Files outside any known folder are not served (P2)

**Goal**: Default deny: an unruled folder or a root-level file is `404` for everyone.

**Independent Test**: A file at `reports/2026.pdf` returns `404` to a leader who is also a member.

- [X] T036 [P] [US4] Integration tests in `server/features/media/tests/integration/test_media_file_api.py` under `DEBUG=False`, as a user with both flags: existing `reports/2026.pdf` → `404`; existing root-level `logo.png` → `404`; look-alikes `gallery-old/x.jpg`, `Gallery/x.jpg` (files present) → `404`; none has `X-Accel-Redirect`.
- [X] T037 [P] [US4] Unit test in `server/features/media/tests/unit/test_media_access_service.py`: the `media_access` log record for `reports/2026.pdf` has `outcome == "unruled"` and `folder is None` (attacker-controlled segment not logged, research R-09). Adjust `_log_decision` in `server/features/media/services/media_access_service.py` if it fails.

---

## Phase 8: User Story 6 — Local development enforces the same rules (P3)

**Goal**: With `DEBUG=True` the same checks apply and the file body is returned directly.

**Independent Test**: Under `DEBUG=True`, a member gets the file bytes; an anonymous caller
gets `401`.

- [X] T038 [P] [US6] Integration tests in `server/features/media/tests/integration/test_media_file_api.py` under `override_settings(DEBUG=True, MEDIA_ROOT=tmp_path)`: member on an existing gallery file → `200`, `b"".join(response.streaming_content)` equals the file bytes, `Content-Type == "image/jpeg"`, `Cache-Control == "private, no-cache"`, no `X-Accel-Redirect`; anonymous → `401`; non-member → `403`.
- [X] T039 [US6] In `server/features/media/views/media_file.py`, add `_direct_file_response(media_file, media_access_service)` returning `FileResponse(media_access_service.open(media_file), content_type=media_file.content_type)` with `Cache-Control = "private, no-cache"`; the view chooses it when `settings.DEBUG` is true (read per request). T038 passes.

---

## Phase 9: Polish & Cross-Cutting

- [X] T040 [P] Rewrite the docstring of `ProfileRepositoryImpl.save_photo` in `server/features/accounts/repositories/profile_repository.py` (FR-020): media is now served only through the authenticated access check (`specs/009-protected-media-access/`); keep the random name as defence in depth against a future nginx edit re-exposing the directory; drop the `TODO/specify_protected_media.md` reference.
- [X] T041 Run `black`, `ruff` and `mypy .` from `server/`; fix findings in the files touched by this feature.
- [X] T042 Run the whole suite (`..\.venv_windows\Scripts\python -m pytest -q` from `server/`) and confirm nothing outside `features/media` regressed — in particular gallery/accounts view tests and any test that fetched media through the removed `static()` route.
- [ ] T043 Run quickstart.md §1 and §2 locally; record the result in the PR description. **Pending:** `runserver` needs the local Postgres, not run in this session; the same scenarios are covered by `TestUnauthenticated` and `TestDevelopmentMode`.
- [X] T044 Check every file touched against CLAUDE.md §8 (functions 4–20 lines, files < 500 lines, explicit types, early returns) and §9 (WHY comments, docstrings with example).
- [X] T045 Hand off the deploy dependencies (spec, Dependencies): nginx change per `contracts/media-endpoint.md` and the app image-loader change; production verification is quickstart.md §4–§5, after the coordinated deploy.

---

## Dependencies & Execution Order

### Phase dependencies

- **Setup (Phase 1)**: none. T001–T003 are docs; T004 skeleton.
- **Foundational (Phase 2)**: after T004. Blocks every story.
- **US1 (Phase 3)**: after Phase 2.
- **US2 (Phase 4)**: after US1 (needs the view and route from T022–T024).
- **US5 (Phase 5)**: after US2 for T029/T031 (they assert on the redirect header); T028 and
  T030 only need Phase 2.
- **US3 (Phase 6)**, **US4 (Phase 7)**: after US2; independent of each other and of US5.
- **US6 (Phase 8)**: after US1.
- **Polish (Phase 9)**: after all stories.

### Deploy gate

US1 + US2 + US5 are the minimum that may reach production — US2 without US5 would ship
redirect generation without the adversarial proof. In practice all phases ship together in
one backend deploy, followed the same day by the app release and then the nginx switch.

### Within each story

Tests first (they must fail), then implementation, then the checkpoint run.

### Commit boundaries (mypy hook checks the whole tree)

1. T001–T003 (docs)
2. T004–T020 (foundation; no route, tree consistent)
3. T021–T032 (US1 + US2 + US5: route live with validation)
4. T033–T035, T036–T037, T038–T039 (one commit each)
5. T040–T045

---

## Parallel Examples

```text
# Phase 2, after T004:
T005, T006, T010, T011, T013, T014, T016, T020   # different files, no mutual dependency
then T007 → T008;  T009;  T012;  T015;  T017 → T018;  T019

# Phase 5:
T028, T029, T030, T031 together, then T032

# After US2 is green:
US3 (T033–T035), US4 (T036–T037) and US6 (T038–T039) can proceed in parallel —
but T034, T036 and T038 all append to test_media_file_api.py, so merge them sequentially.
```

---

## Implementation Strategy

### MVP first

1. Phase 1 → Phase 2 (foundation, all unit-tested).
2. US1 → US2 → US5. **Stop and validate**: quickstart §1–§2. This alone closes the hole
   for gallery and profile photos once nginx switches.

### Incremental

3. US3 (leader rule for the members feature) and US4 (default-deny proof).
4. US6 (dev-mode delivery; until then, local image loading returns the redirect header with
   an empty body).
5. Polish, then the coordinated deploy: backend → app release → nginx switch, same day.

---

## Notes

- `[P]` = different files and no dependency on an unfinished task.
- Tests for the production path use `@override_settings(DEBUG=False)`; `test.py` sets
  `DEBUG=True` (research R-12).
- Never log beyond folder + outcome in the service (FR-019); the request log keeps full paths
  by decision.
- Out of scope, do not fix here: gallery uploads keep the original extension (plan, Out of
  scope).
