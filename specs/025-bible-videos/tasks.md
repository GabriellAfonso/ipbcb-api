# Tasks: Bible Videos and Reading Progress

**Input**: `specs/025-bible-videos/` (plan, spec, research, data-model, contracts/api.md)

**Tests**: required — CLAUDE.md §10 (every new function gets a test; named fakes).

Paths are relative to `server/` unless they start with `specs/`.

## Phase 1: Setup

- [X] T001 Update the domain spec `specs/bible/spec.md`: videos, places, progress, endpoints, errors, business rules (spec before code)
- [X] T002 [P] Add the `bible_videos` scope row and endpoint table to `specs/012-feature-role-permissions/spec.md`
- [X] T003 Turn `features/bible/repositories.py` into package `features/bible/repositories/` (`bible_text.py` + `__init__.py` re-exports) and `features/bible/services.py` into `features/bible/services/` (`bible_service.py` + re-exports); existing tests stay green

## Phase 2: Foundational

- [X] T004 Add `Scope.BIBLE_VIDEOS` in `core/domain/access.py`; `makemigrations core` (PanelScope options); hand-write `core/migrations/0012_bible_videos_scope_for_leader.py` (Liderança owner, reverse removes; reason at top)
- [X] T005 Add `bible_videos` rows to `core/tests/integration/test_management_access_matrix.py` and a migration test that Liderança holds owner and Mídia nothing
- [X] T006 [P] Add `UpstreamUnavailableError` (503) in `core/domain/base_exceptions.py`, map it in `core/http/exceptions.py`, test in `core/tests/unit/`
- [X] T007 [P] Create `core/domain/bible_exceptions.py` (InvalidUrl, Unavailable, LookupFailed, Exists with `video`, PlaceInvalid, OrderMismatch with `expected_video_ids`, VideoNotFound, PlaceNotFound) and re-export in `core/domain/exceptions.py`
- [X] T008 [P] Pure `BibleCanon` in `features/bible/domain/canon.py` (order, chapter counts, case-insensitive resolve, place validation) + `features/bible/tests/unit/test_canon.py`
- [X] T009 `BibleRepository.canon()` in `features/bible/repositories/bible_text.py` (fails if translations disagree or ids collide) + test against the real data files
- [X] T010 Models `features/bible/models/bible_video.py`, `bible_progress.py`, `__init__.py`; `makemigrations bible` → `features/bible/migrations/0001_initial.py`
- [X] T011 [P] DTOs `features/bible/video_dtos.py` and `features/bible/progress_dtos.py` + `features/bible/tests/unit/test_video_dtos.py`, `test_progress_dtos.py`
- [X] T012 Repository protocols in `features/bible/repositories/interfaces.py`; named fakes in `features/bible/tests/fakes.py`

## Phase 3: User Story 1 — Leadership links a video (P1) 🎯 MVP

**Independent test**: Liderança POSTs a link with three places (fake oEmbed) → 201 with title and appended positions; duplicate → 409 with `video`.

- [X] T013 [P] [US1] Pure link parser `features/bible/domain/youtube_links.py` + `features/bible/tests/unit/test_youtube_links.py` (all hosts, `watch?v&list`, `t=` forms, invalid)
- [X] T014 [P] [US1] `HttpYouTubeOEmbedClient` in `features/bible/repositories/youtube_oembed.py` + `features/bible/tests/unit/test_youtube_oembed.py` (fake `requests` session: 200, 401/403/404/400, 5xx, timeout, bad JSON)
- [X] T015 [US1] `BibleVideoRepositoryImpl.find_by_target`, `create` (grouped max + 1), `get` in `features/bible/repositories/video_repository.py` + `features/bible/tests/integration/test_video_repository.py`
- [X] T016 [US1] `BibleVideoService.create` in `features/bible/services/video_service.py` + `features/bible/tests/unit/test_video_service.py`
- [X] T017 [US1] Schema serializers `features/bible/serializers.py`; `BibleVideoListView.post` in `features/bible/views/videos.py`; routes before `<str:name>` in `features/bible/urls.py`; DI in `config/di.py`
- [X] T018 [US1] API tests `features/bible/tests/integration/test_bible_videos_create_api.py` (201, 409, 400s, 503, 403 Mídia, 401)

## Phase 4: User Story 2 — Anyone lists the videos (P1)

**Independent test**: GET without token returns videos with ordered places; ETag → 304.

- [X] T019 [US2] `BibleVideoRepositoryImpl.list_all` (two queries) + repository test
- [X] T020 [US2] `BibleVideoService.list_videos` (places sorted by canon order) + unit test
- [X] T021 [US2] `BibleVideoListView.get` (AllowAny, public ETag) + `features/bible/tests/integration/test_bible_videos_list_api.py`

## Phase 5: User Story 3 — Leadership edits places and order (P2)

**Independent test**: replace places keeps/apends/removes; empty → deleted; reorder one place leaves others.

- [X] T022 [US3] Repository `replace_places`, `remove_place`, `delete`, `video_ids_at`, `set_order` + repository tests
- [X] T023 [US3] Service `replace_places`, `remove_place`, `delete_video`, `set_order` + unit tests
- [X] T024 [US3] Views `BibleVideoPlacesView` (PUT, DELETE), `BibleVideoDetailView` (DELETE), `BibleVideoOrderView` (PUT); URLs
- [X] T025 [US3] API tests `features/bible/tests/integration/test_bible_videos_edit_api.py` (incl. 403 Mídia, 404s, progress cascade on delete)

## Phase 6: User Story 4 — Member progress (P2)

**Independent test**: sync batch → accepted/rejected; older change ignored; GET returns done only.

- [X] T026 [P] [US4] `BibleProgressRepositoryImpl` (`chapter_marks`, `video_marks`, `existing_video_ids`, `save_marks` upsert, `done_state`) in `features/bible/repositories/progress_repository.py` + integration test
- [X] T027 [US4] `BibleProgressService` (`state`, `sync` fold) in `features/bible/services/progress_service.py` + unit tests (LWW, ties, same target twice, reasons, future, offset)
- [X] T028 [US4] Views `features/bible/views/progress.py` (GET private ETag, POST sync), URLs, DI
- [X] T029 [US4] API tests `features/bible/tests/integration/test_bible_progress_api.py` (401, isolation, 400 shape/size, user delete cascade)

## Phase 7: Polish

- [X] T030 `python manage.py makemigrations --check`, OpenAPI schema generates with no new warnings
- [X] T031 Full suite + pre-commit (mypy, ruff, black, bandit)
- [X] T032 Mark `specs/bible/tasks.md` / this file done

## Dependencies

Setup → Foundational → US1 → (US2, US3 need US1's repository/service; US4 only needs Foundational) → Polish.
US4 can run in parallel with US2/US3.

## Parallel examples

- Foundational: T006, T007, T008, T011 together.
- US1: T013 and T014 together, before T015–T018.

## Implementation strategy

MVP = US1 + US2 (create and list). Then US3, US4; one commit for spec + code at the end.
