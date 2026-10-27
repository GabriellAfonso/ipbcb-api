# Research: Gallery Videos

Decisions taken while planning `specs/023-gallery-videos/spec.md`. Each has the decision, why,
and what was rejected.

## R-01 — A video is a `Photo` row with a media type

**Decision**: `Photo` gains `media_type` (`photo` | `video`, default `photo`), `duration_ms`
(`PositiveIntegerField`, null) and `file_size` (`PositiveBigIntegerField`, null). Model, table and
routes keep their names.

**Rationale**: decided by the user (spec Context). Tags, trash, purge, ordering, move, change feed,
the trashed-file media check and the app's sync all key on `Photo`; every one of them works for a
video with no change.

**Alternatives**: a `Video` model, or a generic `MediaItem` with a rename — both duplicate or
rewrite every gallery path for no behaviour gain.

## R-02 — `Photo.image` becomes a `FileField`

**Decision**: change `image` from `ImageField` to `FileField` (same column, `varchar(100)`; the
generated `AlterField` emits no SQL on PostgreSQL). `thumbnail` stays an `ImageField`: it is
always a JPEG.

**Rationale**: `ImageField` validates by decoding when a form handles it (`forms.ImageField`), and
its name promises an image. Today no form edits it (read-only in the admin), but the field type is
the one place that makes FR-005 true for every future path, not only the current ones. The
stored name and URL are unchanged, so nothing reading `image.name` / `image.url` changes.

**Alternatives**: a second `video` file field — every reader (`_to_view`, purge file names,
trashed-file lookup and its partial index, media check) would have to look in two columns; keeping
`ImageField` — works today, but relies on nobody ever putting it in a form.

## R-03 — Format detection by signature, in `core/files/video_validation.py`

**Decision**: `detect_video_extension(upload, max_bytes=MAX_VIDEO_BYTES) -> "mp4" | "mov"`,
next to `image_validation.py`, same shape: size from `upload.size` first (no byte read), then the
first 12 bytes:

- bytes 4–8 `ftyp`: major brand (bytes 8–12) `qt  ` → `mov`; brand in the refused set
  (`3gp*`, `3g2*`, `M4A `, `M4B `, `M4P `, `F4A `, `F4B `, `heic`, `heix`, `heim`, `heis`,
  `hevc`, `hevx`, `mif1`, `msf1`, `avif`, `avis`, `jp2 `, `crx `) → refused; any other → `mp4`.
- bytes 4–8 `moov`, `mdat`, `wide`, `free` or `skip` → `mov` (QuickTime files without `ftyp`).
- anything else, or fewer than 12 bytes → refused.

Messages in Portuguese (they reach the uploader): "Formato de vídeo não suportado. Use MP4 ou
MOV." and "Vídeo muito grande: {size} bytes. O máximo é 104857600 bytes (100 MB)."

**Rationale**: no ffprobe in the image (spec FR-014). A deny-list of brands keeps every real
phone/editor MP4 brand (`isom`, `iso2`–`iso6`, `mp41`, `mp42`, `avc1`, `M4V `, `dash`, …)
accepted, while refusing the ISO-BMFF files that are not MP4 video. The app checks codecs, so a
broken MP4 is its problem, not the server's.

**Alternatives**: an allow-list of brands — refuses a legitimate file from an unusual encoder,
which the uploader cannot fix; `python-magic` — a new native dependency for 30 lines of code.

The size helper `_upload_size` of `image_validation.py` moves to `core/files/upload_size.py`
(public `upload_size`) so both validators and the gallery's `file_size` share it (CLAUDE.md §8, no
duplication).

## R-04 — Upload fields and check order

**Decision**: multipart `album_id`, `video`, `poster`, `duration_ms`, `client_upload_id`,
optional `date_taken`. Order:

1. permission (unchanged `member_read_gallery_write_permissions`);
2. view: `album_id` integer; `image` and `video` not both; exactly one `video`, one `poster`;
   `duration_ms`, `client_upload_id`, `date_taken` each at most once; types through
   `VideoUploadSerializer` (`duration_ms` 1 … 2 147 483 647, `date_taken` `DateField`, empty →
   `null`);
3. service: client upload id shape (`ensure_valid_client_upload(id, 1)`), then lookup — repeat
   answered as spec 016;
4. album exists; video size and signature; poster validation, pixel limit, thumbnail; then write.

**Rationale**: same order as spec 016 (shape before lookup, lookup before album). `image` keeps
meaning "photo" (decided). The serializer satisfies CLAUDE.md §3 (input to the database through a
serializer); the count checks run first because a `QueryDict` hands a serializer only the last
value of a repeated field.

## R-05 — Service: `GalleryService.upload_video`, shared write path

**Decision**: `upload_video(album_id, video, poster, upload: VideoUploadMeta, uploader_id)` on
`GalleryService`. It reuses `_existing_upload`, `_persist` and the automatic cover; the race
fallback of `_store_first` is generalised into `_answer_race(client_upload_id, uploader_id,
store)` used by both photo and video. Refusals of the video or the poster are wrapped into
`NoVideoAcceptedError` (subclass of `NoPhotoAcceptedError`, detail "O vídeo não foi aceito.",
`rejected` = `[{filename: <video name>, reason}]`; a poster reason is prefixed with "Imagem de
capa: ").

**Rationale**: the write path (files first, row, cleanup on failure, cover) must be identical for
both media (FR-017, FR-018), so it stays in one class; `gallery_service.py` grows from 263 to about
340 lines, under the 500 limit. A subclass keeps the canonical 400 body and handler untouched.

**Alternatives**: a separate `VideoUploadService` — would need the same private helpers made
public or copied.

## R-06 — `file_size` recorded on every upload, backfilled by a command

**Decision**: `NewPhoto` carries `file_size` (from `upload_size`) and `media_type` and
`duration_ms`; the repository writes them. `fill_gallery_file_sizes` (management command) calls
`GalleryService.fill_missing_file_sizes()`, which reads `(id, image name)` of rows with
`file_size IS NULL`, asks the storage for the size (`GalleryFileStorage.size`, new) and writes it
with a new `updated_at`; a missing file is skipped and listed. Idempotent because only `NULL` rows
are read.

**Rationale**: decided ("preenchido por um comando único"); same shape as
`generate_photo_thumbnails`. A data migration would stat every file inside `migrate` at deploy,
and fail the deploy on a slow disk.

## R-07 — A database check keeps media fields consistent

**Decision**: one `CheckConstraint`, `photo_media_fields_match_type`: `media_type = 'photo' AND
duration_ms IS NULL` or `media_type = 'video' AND duration_ms IS NOT NULL AND thumbnail <> ''`.

**Rationale**: SC-002 says no path may create a video without poster or duration; the admin
shell or a future path is covered by the database, not only the service. Photos are not required
to have a thumbnail (pre-013 rows may not).

## R-08 — Other paths

- `photos_without_thumbnail` filters `media_type = 'photo'` (FR-025).
- Media check: `_CONTENT_TYPES` gains `mp4 → video/mp4`, `mov → video/quicktime` (FR-022).
- Admin `PhotoAdmin`: the three fields read-only; `image` read-only already, rendered as a link.
- Album cover from a video in the app: `PUT /api/albums/{id}/cover/` with the poster image; no
  backend change.
- Trash entries, purge, trashed-file lookup: unchanged (they read `image` and `thumbnail` names).

## R-09 — Upload size, buffering and Range

- nginx (`nginx-deploy` `c954a67`): `client_max_body_size 110M` in `location /ipbcb/`, request
  buffering on (default), Range answered by the `internal` location. Verified by reading the
  config; the end-to-end `206` check is a production step (quickstart §5).
- Django: `FILE_UPLOAD_MAX_MEMORY_SIZE` default 2.5 MB → a video streams to a temporary file;
  `DATA_UPLOAD_MAX_MEMORY_SIZE` does not count file parts; no setting overrides either.
- gunicorn `--timeout 60` (`compose.prod.yml`): the worker gets the request only once nginx has
  the whole body, and reads it over the local network, so a slow phone never holds it.
- `Cache-Control: private, no-cache` from Django does not affect Range: nginx answers `Range` on
  a static file regardless of upstream cache headers.

## R-10 — Migration

One generated migration `gallery/0007`: three `AddField`, one `AlterField` (`image`), one
`AddConstraint`. Existing rows get `media_type = 'photo'` from the default and `NULL` for the
other two, which satisfies the check. No hand-written or data migration.
