# Data Model: Gallery Videos

## Photo (changed)

A gallery item: a photo or a video. Fields not listed are unchanged (`specs/gallery/spec.md`).

| Field       | Type                         | Constraints                                                  |
|-------------|------------------------------|--------------------------------------------------------------|
| image       | **FileField** (was ImageField) | `gallery/{album_id}/{uuid}.{ext}`; a video's file for videos |
| thumbnail   | ImageField                   | blank; the poster's 1000 px JPEG for videos                  |
| media_type  | CharField(5)                 | `photo` \| `video`; default `photo`                          |
| duration_ms | PositiveIntegerField, null   | set ⇔ video                                                  |
| file_size   | PositiveBigIntegerField, null | bytes of `image`; set on every upload, backfilled for older rows |

- `ext`: decoded image format for photos; `mp4` or `mov` from the file signature for videos.
- Check constraint `photo_media_fields_match_type`:
  `(media_type='photo' AND duration_ms IS NULL) OR
   (media_type='video' AND duration_ms IS NOT NULL AND thumbnail <> '')`.
- `media_type`, `duration_ms` and `file_size` are written by the upload (and `file_size` by the
  backfill command) and never edited; the admin shows them read-only.

## DTOs

- `PhotoView` + `media_type: Literal["photo", "video"] = "photo"`, `duration_ms: int | None =
  None`, `file_size: int | None = None`.
- `NewPhoto` + the same three fields.
- `VideoUploadMeta` (new): `duration_ms: int`, `date_taken: date | None`, `client_upload_id: str`.
- `FileSizeBackfillReport` (new): `filled: int`, `skipped_ids: list[int]`.

## Domain constants

- `features/gallery/domain/media_types.py`: `PHOTO`, `VIDEO`, `MediaType` literal.
- `core/files/video_validation.py`: `MAX_VIDEO_BYTES = 100 * 1024 * 1024`.
