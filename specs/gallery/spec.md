# Gallery

Photo gallery organized by albums. Members browse photos via API; admins upload via Django admin.

---

## Data Models

### Album

| Field | Type             | Constraints    |
|-------|------------------|----------------|
| id    | int (PK, auto)   |                |
| name  | CharField(100)   | unique         |

### Photo

| Field       | Type              | Constraints                        |
|-------------|-------------------|------------------------------------|
| id          | int (PK, auto)    |                                    |
| album       | FK -> Album       | CASCADE, related_name="photos"     |
| name        | CharField(100)    |                                    |
| description | TextField         | blank                              |
| image       | ImageField        | upload_to=`gallery/{slug}/{file}`  |
| date_taken  | DateField         | blank, null                        |
| uploaded_at | DateTimeField     | auto_now_add                       |

Upload path: `gallery/{slugify(album.name)}/{filename}`.

---

## API Endpoints

All API endpoints require `IsMemberUser` permission.

### GET /api/photos/

List all photos across all albums.

- Order: `album__name`, `uploaded_at`
- Response: `200` with array of Photo resources

### GET /api/albums/{album_id}/photos/

List photos from a specific album.

- Order: `uploaded_at`
- Response: `200` with array of Photo resources
- Returns empty list if album does not exist or has no photos

### Photo Resource

```json
{
  "id": 1,
  "name": "foto.jpg",
  "description": "",
  "album_id": 1,
  "album_name": "Culto",
  "image_url": "http://host/ipbcb/media/gallery/culto/foto.jpg",
  "date_taken": "2026-01-15",
  "uploaded_at": "2026-01-15T10:00:00Z"
}
```

`image_url` is an absolute URI built from the request. Returns `null` if image is missing or request is unavailable.

The file behind `image_url` is readable only by members: `/ipbcb/media/gallery/...` goes
through the authenticated media access check (`specs/009-protected-media-access/`), which
requires the same `Profile.is_member` as the endpoints listing it. Holding the URL is not
enough — the request must carry the member's JWT.

---

## Admin Upload

Accessible at `/admin/gallery/album/upload/` (protected by Django admin login).

The API has no gallery write endpoint yet. When it gets one, it belongs to scope `gallery`:
Admin `owner`, Liderança and Mídia `manage` (`specs/012-feature-role-permissions/`). Until then
the Mídia role has nothing to manage here.

### GET

Renders HTML form with:
- Album dropdown (all albums)
- Multi-file image input (accept `image/*`)
- CSRF token

### POST

Accepts `album` (ID) and `images` (file list).

**Validation rules:**
- Album and at least one file must be provided
- Delegated to `core.files.image_validation.detect_image_extension`, shared with the
  profile photo upload: max 10 MB, and the file must decode as JPEG, PNG, WEBP or GIF
- Raised per file and caught per file, so one bad file never fails the batch

**Behavior:**
- Valid files create Photo records linked to selected album
- Invalid files accumulate errors; valid files in same batch still upload
- On full success: redirect to `admin:gallery_album_changelist`
- On errors: re-render form with red error messages

**Error messages (user-facing, Portuguese):**
- Missing album/files: "Selecione um album e ao menos uma imagem."
- Oversized: "{filename}: Arquivo muito grande: {n} bytes. O maximo e {max} bytes (10 MB)."
- Invalid format: "{filename}: Formato invalido: o arquivo enviado nao e uma imagem
  legivel. Use JPEG, PNG, WEBP ou GIF."
- Both come from `core.files.image_validation`, which is why its messages are in
  Portuguese: they reach the user verbatim

---

## Admin Registration

- `Album`: registered with custom upload URL (`/admin/gallery/album/upload/`)
- `Photo`: registered with default admin
