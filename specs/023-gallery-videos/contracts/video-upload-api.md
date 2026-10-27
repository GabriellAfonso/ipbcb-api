# Contract: Gallery Videos

Changes to `specs/013-gallery-write-api/contracts/gallery-api.md` and
`specs/016-photo-upload-idempotency/contracts/photo-upload-api.md`. Everything not listed is
unchanged.

## Photo resource

Three fields appended after `members`:

```json
{
  "id": 52,
  "name": "VID_20260314_101500.mp4",
  "description": "",
  "album_id": 7,
  "album_name": "Retiro 2026",
  "image_url": "http://host/ipbcb/media/gallery/7/9b1e….mp4",
  "thumbnail_url": "http://host/ipbcb/media/gallery/thumbs/7/c4d0….jpg",
  "date_taken": "2026-03-14",
  "uploaded_at": "2026-03-15T10:00:00Z",
  "position": 12,
  "members": [],
  "media_type": "video",
  "duration_ms": 45000,
  "file_size": 41943040
}
```

- `media_type`: `"photo"` or `"video"`.
- `duration_ms`: integer for a video, `null` for a photo.
- `file_size`: bytes of the file behind `image_url`; `null` only for a photo stored before this
  feature whose size was not backfilled (file missing).
- For a video, `image_url` is the video file and `thumbnail_url` its poster.

Returned by `GET /api/photos/`, `GET /api/albums/{id}/photos/`, `GET /api/gallery/changes/`,
`POST /api/photos/`, `PATCH /api/photos/{id}/` and both tag writes.

## POST /api/photos/ — video upload

Permission unchanged (`manage` on `gallery`). Multipart:

| Field              | Required | Shape                                                         |
|--------------------|----------|---------------------------------------------------------------|
| `album_id`         | yes      | integer                                                       |
| `video`            | yes      | exactly one file, MP4 or MOV by signature, ≤ 104 857 600 bytes |
| `poster`           | yes      | exactly one image, validated as a photo (10 MB, JPEG/PNG/WEBP/GIF, 50 MP) |
| `duration_ms`      | yes      | integer 1 … 2 147 483 647, sent once                          |
| `client_upload_id` | yes      | spec 016 shape, sent once                                     |
| `date_taken`       | no       | `YYYY-MM-DD`, sent at most once; empty = `null`               |

Sending `image` together with `video` is refused. Without `video`, the request is the photo
upload, unchanged.

| Outcome                                   | Status | Body |
|-------------------------------------------|--------|------|
| stored                                    | `201`  | `{"accepted": [<Photo>], "rejected": []}` |
| repeat of a live item's `client_upload_id`| `201`  | same, the stored item as it is now; nothing examined or stored |
| repeat of a trashed item's id             | `409`  | `CONFLICT`, `client_upload_id` (spec 016) |
| video or poster refused                   | `400`  | `VALIDATION_ERROR`, detail "O vídeo não foi aceito.", `rejected: [{"filename": "<video name>", "reason": "…"}]` |
| shape error (missing/repeated field, `image`+`video`, bad `duration_ms`/`date_taken`/`client_upload_id`) | `400` | `VALIDATION_ERROR` naming the field |
| unknown album                             | `404`  | `NOT_FOUND` |

Refusal reasons (Portuguese, shown to the uploader):

- `Vídeo muito grande: {size} bytes. O máximo é 104857600 bytes (100 MB).`
- `Formato de vídeo não suportado. Use MP4 ou MOV.`
- `Imagem de capa: {reason of the image validation}`

## Media files

`GET /ipbcb/media/gallery/…/{uuid}.mp4` → `Content-Type: video/mp4`; `.mov` → `video/quicktime`.
Same access rules and `Cache-Control: private, no-cache`. In production `Range: bytes=N-` answers
`206 Partial Content` with `Content-Range` (nginx, after the media check).

## Management command

`python manage.py fill_gallery_file_sizes` — prints `filled N, skipped M: ids [...]`. Idempotent.
