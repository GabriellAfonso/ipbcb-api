# Implementation Plan: Gallery Videos

**Branch**: `023-gallery-videos` | **Date**: 2026-10-26 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/023-gallery-videos/spec.md`

## Summary

A video is a `Photo` row with `media_type = "video"`. `Photo` gains `media_type`, `duration_ms`
and `file_size`; `image` becomes a `FileField` so nothing ever decodes a video as an image; a check
constraint keeps a video from existing without duration or poster. `POST /api/photos/` accepts a
second request shape — `video` + `poster` + `duration_ms` + `client_upload_id` (+ optional
`date_taken`) — checked by the view and a serializer, then `GalleryService.upload_video`, which
reuses the spec 016 retry lookup, the photo write path (files first, row, cleanup) and the automatic
cover from the poster. The video format comes from its first bytes (`core/files/video_validation.py`,
100 MB, MP4/MOV), never from ffprobe. The resource gains three fields; the media check serves
`mp4`/`mov`; a one-off command backfills `file_size`. nginx is already done.

## Technical Context

**Language/Version**: Python 3.14, `.venv_windows`

**Primary Dependencies**: Django 6.0, DRF 3.17, dependency-injector, Pydantic 2.12, Pillow (poster
only). No new dependency; no ffmpeg/ffprobe.

**Storage**: PostgreSQL in production, SQLite in tests; files on Django's default storage under
`gallery/`. One generated migration, `gallery/0007` (R-10).

**Testing**: pytest + pytest-django; named fakes in `features/gallery/tests/fakes.py`
(`FakeGalleryRepository`, `FakeGalleryFileStorage` extended); mypy, ruff, bandit via pre-commit.

**Target Platform**: Linux container (gunicorn + uvicorn workers) behind nginx, prefix `/ipbcb/`.

**Project Type**: Web service (REST API), single Android client.

**Performance Goals**: a video upload costs one size check, a 12-byte read, the poster's thumbnail
and one file copy; no pass over the video's content.

**Constraints**: existing resource fields, routes and photo behaviour unchanged (FR-007, FR-020);
admin upload page untouched (FR-021); services never see HTTP; ORM only in repositories;
migrations 0001–0006 untouched; files under 500 lines, functions 4–20 lines.

**Scale/Scope**: low thousands of items; one endpoint-method extended, three fields, one command.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design; result unchanged.*

| Rule (`specs/constitution.md`, `CLAUDE.md`) | Status |
|---|---|
| `IsAuthenticated` + scope on the write | ✅ unchanged `member_read_gallery_write_permissions` |
| Views → services → repositories; ORM only in repositories | ✅ new reads/writes in `GalleryRepositoryImpl`; sizes through `GalleryFileStorage` |
| Services never import HTTP objects | ✅ `upload_video` receives files and a `VideoUploadMeta` DTO |
| Input validated before the database | ✅ count checks + `VideoUploadSerializer` in the view; signature, size, poster in the service |
| Domain exceptions with offending value and expected shape | ✅ `NoVideoAcceptedError`; validator messages carry size/format |
| DI via `config/di.py` | ✅ no new provider; the new command module added to wiring |
| DTOs are Pydantic | ✅ `VideoUploadMeta`, `FileSizeBackfillReport`; `PhotoView`/`NewPhoto` + fields |
| Third-party libs behind own interface | ✅ no new library; Pillow stays behind `ImageProcessor` |
| Structured JSON logs | ✅ unchanged events; no new log line needed |
| Migrations generated; applied ones untouched | ✅ `makemigrations` only (R-10) |
| Spec before code; spec and code in the same commit | ✅ `specs/gallery/spec.md` updated first (T001) |
| Functions 4–20 lines, files < 500 lines | ✅ `gallery_service.py` ≈ 340 lines; video sniffing in its own module |
| Tests for every new function; named fakes | ✅ see tasks |

Gate: **pass**. No deviations.

## Technical Decisions

Full reasoning in [research.md](research.md).

- **D-1** `Photo.media_type` / `duration_ms` / `file_size`; same model and routes (R-01).
- **D-2** `image` becomes `FileField` (R-02).
- **D-3** Signature sniffing in `core/files/video_validation.py`; shared `upload_size` helper
  (R-03).
- **D-4** Fields `video`, `poster`, `duration_ms`, `client_upload_id`, `date_taken`; check order
  of spec 016 (R-04).
- **D-5** `GalleryService.upload_video` sharing the write path; `NoVideoAcceptedError` (R-05).
- **D-6** `file_size` on every upload; `fill_gallery_file_sizes` command (R-06).
- **D-7** Check constraint `photo_media_fields_match_type` (R-07).
- **D-8** Thumbnail backfill skips videos; media content types; admin read-only (R-08).
- **D-9** nginx already done; Range checked in production (R-09).

## Project Structure

### Documentation (this feature)

```text
specs/023-gallery-videos/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/video-upload-api.md
└── tasks.md
```

### Source Code

```text
server/
├── core/
│   ├── domain/gallery_exceptions.py          # + NoVideoAcceptedError
│   ├── domain/exceptions.py                  # re-export
│   └── files/
│       ├── upload_size.py                    # new: shared size helper
│       ├── image_validation.py               # uses upload_size
│       └── video_validation.py               # new: detect_video_extension
├── features/gallery/
│   ├── domain/media_types.py                 # new: PHOTO, VIDEO, MediaType
│   ├── models/gallery.py                     # 3 fields, FileField, check constraint
│   ├── migrations/0007_*.py                  # generated
│   ├── dtos/gallery_dtos.py                  # PhotoView, NewPhoto, VideoUploadMeta, report
│   ├── repositories/gallery_repository.py    # write/read new fields, size backfill queries
│   ├── repositories/gallery_file_storage.py  # + size()
│   ├── repositories/interfaces.py            # protocol additions
│   ├── services/gallery_service.py           # upload_video, fill_missing_file_sizes
│   ├── serializers/serializers.py            # resource fields, VideoUploadSerializer
│   ├── views/gallery.py                      # video branch of POST
│   ├── admin.py                              # read-only fields
│   └── management/commands/fill_gallery_file_sizes.py   # new
├── features/media/domain/media_rules.py      # mp4, mov content types
└── config/di.py                              # wire the new command
```

## Implementation Order

1. Domain spec (`specs/gallery/spec.md`) and 013 contract pointer.
2. Shared helpers: `upload_size`, `video_validation`, media types, exception.
3. Model + migration; DTOs; repository and storage; fakes.
4. Service (`upload_video`, `file_size` on photo upload, backfill); command.
5. Serializers and view; media content types; admin.
6. Tests per layer, then the full suite.

## Complexity Tracking

None.
