# Gallery — Plan

## Decisions already made

- **Layered**: views → services (`GalleryService` for photos, `AlbumService` for albums,
  `AlbumCoverService` for covers) → repositories (`GalleryRepository`, `AlbumRepository`) →
  models. Services exchange Pydantic DTOs (`AlbumView`, `PhotoView`, `UploadResult`, …) and are
  registered in `config/di.py`.
- **Upload validation** stays in `core.files.image_validation` (decoded content, 10 MB, JPEG /
  PNG / WEBP / GIF), shared with profile and member photos.
- **Image derivatives** (thumbnails, covers) go through the project-owned `ImageProcessor`
  Protocol; `PillowImageProcessor` is the only derivative code that imports Pillow.
- **Files** go through `GalleryFileStorage` on Django's `default_storage`, under random names.
  Files are written before the row; a failed transaction deletes them; a replaced cover is
  deleted after commit.
- **Sibling-unique names** by two conditional unique constraints (per parent, and among roots),
  plus a service pre-check for the message.
- **Tree order and cover inheritance** computed in memory from the whole album table (one
  query), by pure functions in `features/gallery/domain/album_tree.py` that tolerate a cycle.
  Nothing about inheritance is stored.
- **Cycle check** under `select_for_update` of the album rows, so two concurrent moves cannot
  build a cycle together.
- **Positions** appended as `max + 1` under a lock of the parent row; reorder is a full list
  applied with one `bulk_update`.
- **Mixed-permission routes** (`/api/albums/`, `/api/photos/`: member reads, `gallery` writes)
  pick permissions per method in `get_permissions()`.
- **DRF APIView** (no ViewSets); **no pagination**; **`select_related("album")`** on photo
  queries.
- **Django admin** keeps the upload page and album editing, both through the services.

Full reasoning: `specs/013-gallery-write-api/plan.md` (D-1 … D-12) and `research.md`.
