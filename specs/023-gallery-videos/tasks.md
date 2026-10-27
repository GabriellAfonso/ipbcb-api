# Tasks: Gallery Videos

**Input**: `specs/023-gallery-videos/` (spec, plan, research, data-model, contracts, quickstart)

Paths are relative to `server/` unless they start with `specs/`.

## Phase 1: Spec first

- [x] T001 Update `specs/gallery/spec.md`: Photo table (`image` FileField, `media_type`,
  `duration_ms`, `file_size`, check constraint), POST video upload section, resource fields,
  media types, backfill command, thumbnail command skipping videos, errors table.

## Phase 2: Foundational (blocks every story)

- [x] T002 [P] Move the size helper to `core/files/upload_size.py` (`upload_size`), use it in
  `core/files/image_validation.py`; test in `core/files/tests/` or the existing validation tests.
- [x] T003 [P] `core/files/video_validation.py`: `MAX_VIDEO_BYTES`, `detect_video_extension`
  (R-03) + unit tests (MP4 brands, `qt  `, classic atoms, refused brands, MKV/WEBM/AVI/JPEG,
  short file, oversize without read).
- [x] T004 [P] `features/gallery/domain/media_types.py` (`PHOTO`, `VIDEO`, `MediaType`).
- [x] T005 [P] `NoVideoAcceptedError` in `core/domain/gallery_exceptions.py`, re-exported from
  `core/domain/exceptions.py`.
- [x] T006 `Photo` model: `image` FileField, three fields, check constraint; generate
  `gallery/0007` with `makemigrations`.
- [x] T007 DTOs: `PhotoView`/`NewPhoto` + fields, `VideoUploadMeta`, `FileSizeBackfillReport`.
- [x] T008 Repository: write/read the new fields; `photos_without_thumbnail` photos only;
  `items_without_file_size`, `set_file_size`; storage `size()`; protocols; fakes.

## Phase 3: User Story 1 — Upload a video (P1)

- [x] T009 [US1] `GalleryService.upload_video` + shared race helper; photo upload records
  `file_size` and `media_type`.
- [x] T010 [US1] `VideoUploadSerializer` and the video branch of `PhotoListAPIView.post`.
- [x] T011 [US1] Unit tests (service with fakes) and API tests: accepted MP4/MOV, oversize,
  wrong format, poster missing/invalid, duration/date shapes, `image`+`video`, two videos,
  missing `client_upload_id`, repeat → 201, trashed repeat → 409, first cover from poster, files
  removed when the row fails, unknown album 404.

## Phase 4: User Story 2 — Members see and download videos (P1)

- [x] T012 [US2] `PhotoSerializer` gains `media_type`, `duration_ms`, `file_size` (last).
- [x] T013 [US2] `media_rules._CONTENT_TYPES` + `mp4`, `mov`; update comment; tests.
- [x] T014 [US2] Tests: resource fields in lists and change feed; media endpoint content type for
  a stored video.

## Phase 5: User Story 3 — Videos behave as photos (P2)

- [x] T015 [US3] Admin: new fields read-only; tests that a video's admin page renders.
- [x] T016 [US3] Tests: tag, trash/restore, purge deletes video + poster, move, `PATCH` refuses
  `media_type`.

## Phase 6: User Story 4 — Sizes of existing photos (P3)

- [x] T017 [US4] `GalleryService.fill_missing_file_sizes` + `fill_gallery_file_sizes` command,
  wired in `config/di.py`; tests (filled, missing file skipped, idempotent, `updated_at` bumped).
- [x] T018 [US4] `generate_photo_thumbnails` skips videos (repository filter; no test: the check
  constraint makes a video without thumbnail impossible to store, so the case cannot be built).

## Phase 7: Polish

- [x] T019 `makemigrations --check`, migrate forward and back (quickstart §2).
- [x] T020 Gallery + media + core tests, then full suite; mypy and ruff through pre-commit.
- [ ] T021 Production steps (after deploy, by the user): backfill command and Range check
  (quickstart §4, §5).
