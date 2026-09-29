# Data Model: Idempotent Photo Upload

## Photo *(existing, one field added)*

| Field            | Type                    | Constraints                                               |
|------------------|-------------------------|-----------------------------------------------------------|
| client_upload_id | CharField(64), null     | `editable=False`; unique among all rows (live and trashed) when set; never serialized |

- Constraint `unique_photo_client_upload_id` on `(client_upload_id)`; `NULL`s never collide
  (research R-01).
- Written once, by the insert of the first upload that carried it; nothing updates or clears it
  (spec FR-008). Freed only when the purge deletes the row (FR-011).
- Not part of `PhotoView`, the Photo resource, the feed, the trash listing or any admin form.
- Every other field and constraint is unchanged (`specs/gallery/spec.md`).

Migration: generated `features/gallery/migrations/0006_photo_client_upload_id.py`, `AddField` +
`AddConstraint`; existing rows `NULL` (R-09).

## Validation rules *(pure, `features/gallery/domain/upload_rules.py`)*

| Rule | Value | Error |
|------|-------|-------|
| length | 1 … `CLIENT_UPLOAD_ID_MAX_LENGTH` = 64 | `InvalidClientUploadIdError` (400) |
| characters | ASCII `A–Z a–z 0–9 - _` | `InvalidClientUploadIdError` (400) |
| files with an id | exactly 1 | `ClientUploadNeedsOneFileError` (400) |
| field repeated | at most once (view, `optional_single_value`) | `ValidationError` (400) |

## DTOs *(`features/gallery/dtos/gallery_dtos.py`)*

- `NewPhoto` *(existing)* + `client_upload_id: str | None = None`.
- `ClientUploadMatch` *(new)*: `photo_id: int`, `trashed: bool` — what the repository knows about
  the row carrying an id.
- `UploadResult` *(unchanged)*: a deduplicated answer is `accepted=[view]`, `rejected=[]`, so the
  view answers `201` with no new branch.

## Repository *(`GalleryRepository` Protocol + `GalleryRepositoryImpl`)*

- `find_client_upload(client_upload_id: str) -> ClientUploadMatch | None` — reads
  `Photo.all_objects`.
- `create_photo(photo: NewPhoto) -> PhotoView` — also writes `client_upload_id`; raises
  `ClientUploadIdTakenError` when the insert hits the constraint (R-04).

## Exceptions *(`core/domain/gallery_exceptions.py`, re-exported)*

| Exception | Base | Status | Extra body |
|-----------|------|--------|------------|
| `InvalidClientUploadIdError` | `ValidationError` | 400 | `client_upload_id` (truncated to 64), `expected` |
| `ClientUploadNeedsOneFileError` | `ValidationError` | 400 | `file_count` |
| `UploadedPhotoTrashedError` | `ConflictError` | 409 | `client_upload_id` |
| `ClientUploadIdTakenError` | `ConflictError` | — | internal: repository → service, never reaches HTTP |

## State of an id

```text
(no row) --first upload stored--> live --DELETE--> trashed --purge--> (no row)
                                   ^                  |
                                   +----restore-------+
```

| State of the row carrying the id | Answer to a request with that id |
|----------------------------------|----------------------------------|
| no row (never used, or purged)   | first upload (013 behaviour, id stored) |
| live                             | `201`, `accepted: [current resource]`, nothing stored |
| trashed                          | `409` `CONFLICT`, nothing stored |
