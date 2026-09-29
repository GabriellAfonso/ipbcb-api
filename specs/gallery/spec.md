# Gallery

Photo gallery organized in a tree of albums. Members browse it through the API; the Mídia,
Liderança and Admin roles build it — albums, photos, covers and order — through the API from the
app's management panel. Deleting sends items to a 30-day trash from which they can be restored;
a daily purge then removes them with their files. A change feed lets the app sync only what
changed, deletions included. Managers tag the members who appear in a photo; every member sees
the tags and can filter photos by the people in them. The Django admin keeps an upload page and
album editing, going through the same services, and cannot delete.

Write API introduced by `specs/013-gallery-write-api/`; trash, purge and change feed by
`specs/014-gallery-trash-sync/`; member tags by `specs/015-gallery-member-tags/` (design,
research and contracts there).

---

## Permissions

- **Reads** (`GET`) of the gallery itself and the change feed require membership: `IsMemberUser`
  (`Profile.is_member`).
- **Writes** require scope `gallery` (`specs/012-feature-role-permissions/`) at the method's
  default level: `manage` for `POST`/`PUT`/`PATCH`, `owner` for `DELETE`.
- **Trash** (`GET /api/gallery/trash/`) and **restore** (`POST …/restore/`) require `owner` on
  `gallery`, declared as overrides above the method default.
- **Tag picker** (`GET /api/gallery/taggable-members/`) requires `manage` on `gallery`, declared
  as an override above `view`. It is the one place the Mídia role reads member data — names only
  (`specs/012-feature-role-permissions/`, User Story 3). The tagged-member list and the
  `member_id` filter are member reads.
- Admin, Liderança and Mídia all hold `owner` on `gallery` (raised from `manage` for Liderança
  and Mídia by `core/migrations/0006_gallery_owner_for_leader_media.py`).
- A caller without the permission gets `403` before existence is checked.

---

## Data Models

### Album

| Field       | Type                 | Constraints                                                 |
|-------------|----------------------|-------------------------------------------------------------|
| id          | int (PK, auto)       |                                                             |
| name        | CharField(100)       | trimmed, non-blank; unique among siblings, roots included   |
| parent      | FK -> Album, null    | PROTECT, related_name="children"; `null` = root             |
| description | TextField            | blank, default ""                                           |
| event_date  | DateField            | null                                                        |
| position    | PositiveIntegerField | order among siblings                                        |
| cover_image | ImageField           | blank; `gallery/covers/{album_id}/{uuid}.jpg`               |
| deleted_at  | DateTimeField, null  | set ⇔ in the trash                                          |
| deletion_batch | FK -> GalleryDeletionBatch, null | PROTECT; set and cleared with `deleted_at`   |
| updated_at  | DateTimeField        | indexed; set by every change, derived ones included (feed)  |

- Uniqueness among **live** albums only: two conditional unique constraints, `(parent, name)`
  when `parent` is set and `(name)` when it is not, both with `deleted_at IS NULL`. A plain
  `(parent, name)` constraint would let roots repeat a name, since SQL `NULL`s are distinct; a
  trashed album never holds its name.
- The default manager (`Album.objects`) returns live albums only; `Album.all_objects` returns
  every row and is used only by the trash, restore, purge and media-lookup code.
- The tree has no depth limit and never contains a cycle: an album cannot be moved under itself
  or any of its descendants.
- An album may hold photos and sub-albums at the same time.
- Rows are only ever deleted by the purge, which deletes descendants before their parents
  (`PROTECT`).

### Photo

| Field       | Type                  | Constraints                                               |
|-------------|-----------------------|-----------------------------------------------------------|
| id          | int (PK, auto)        |                                                           |
| album       | FK -> Album           | PROTECT, related_name="photos"                            |
| name        | CharField(100)        | original filename, cut keeping the extension              |
| description | TextField             | blank                                                     |
| image       | ImageField            | `gallery/{album_id}/{uuid}.{ext}`                         |
| thumbnail   | ImageField            | blank; `gallery/thumbs/{album_id}/{uuid}.jpg`             |
| date_taken  | DateField             | null; EXIF capture date on upload                         |
| uploaded_at | DateTimeField         | auto_now_add                                              |
| uploaded_by | FK -> User, null      | SET_NULL; auditing only, never serialized                 |
| position    | PositiveIntegerField  | order within the album                                    |
| deleted_at  | DateTimeField, null   | set ⇔ in the trash                                        |
| deletion_batch | FK -> GalleryDeletionBatch, null | PROTECT                                     |
| updated_at  | DateTimeField         | indexed; set by every change, derived ones included       |

- `album` is `PROTECT` so an album row can never take photo rows with it: only the purge deletes
  rows, always with their files.
- Default manager live-only, `Photo.all_objects` for everything, as for albums.
- `ext` comes from the decoded image format, never from the filename.
- Paths carry the album id only to spread files. Renaming or moving an album or a photo never
  moves a file; a moved photo keeps its files under the old album's folder.
- Photos uploaded before feature 013 keep their old path, `gallery/{slugify(album.name)}/{filename}`.
- Photos uploaded before feature 013 have no thumbnail until the
  `generate_photo_thumbnails` command runs; they have no `uploaded_by`.

### PhotoTag

A member who appears in a photo.

| Field      | Type                  | Constraints                                               |
|------------|-----------------------|-----------------------------------------------------------|
| id         | int (PK, auto)        |                                                           |
| photo      | FK -> Photo           | CASCADE, related_name="tags"                              |
| member     | FK -> members.Member  | CASCADE, no reverse accessor on `Member`                  |
| tagged_by  | FK -> User, null      | SET_NULL; auditing only, never serialized                 |
| tagged_at  | DateTimeField         | auditing only, never serialized                           |

- Unique per `(photo, member)`.
- Only member records can be tagged; `Member.is_active` plays no part (inactive members are
  offered, tagged and shown).
- A tag follows its photo: kept and invisible while the photo is in the trash, back on restore,
  removed by the purge. Deleting a member removes its tags.
- Written only through the two tag endpoints; the Django admin shows tags read-only on the photo
  page and does not register `PhotoTag`.
- Member names reach the gallery through this relation; the picker reads the roll through the
  `MemberDirectory` port that `features/members` implements (wired in `config/di.py`), so neither
  feature imports the other.

### GalleryDeletionBatch

Everything one delete action sent to the trash.

| Field      | Type                 | Constraints                                          |
|------------|----------------------|------------------------------------------------------|
| id         | UUID (PK)            |                                                      |
| root_kind  | `album` / `photo`    | the kind of item the delete was made on              |
| root_id    | PositiveIntegerField | its id (no FK); unique with `root_kind`              |
| deleted_at | DateTimeField        | indexed                                              |
| deleted_by | FK -> User, null     | SET_NULL                                             |

### GalleryDeletionMark

What the change feed reports as deleted. Survives the purge.

| Field      | Type                 | Constraints                                  |
|------------|----------------------|----------------------------------------------|
| kind       | `album` / `photo`    | unique with `object_id`                      |
| object_id  | PositiveIntegerField | no FK                                        |
| deleted_at | DateTimeField        | indexed                                      |

---

## Ordering

- Albums order among siblings by `position`, then `id`; photos within an album likewise.
- Created, uploaded and moved items go to the end of their new siblings.
- **Tree order**: depth-first, pre-order walk of the album tree, siblings by `position` then `id`.
- Reordering replaces the whole order of one set of siblings. The request lists every current
  sibling exactly once; a missing, unexpected, nonexistent or repeated id is `400` and nothing
  changes.

---

## Image Derivatives

| Derivative      | Shape                                           | Format           |
|-----------------|-------------------------------------------------|------------------|
| Album cover     | 1000×1000 px square, center-cropped             | JPEG, quality 85 |
| Photo thumbnail | longest side 1000 px, aspect kept, no crop, no upscale | JPEG, quality 85 |

- Each size is one constant in its service.
- Animated GIFs use the first frame; transparency is flattened onto white; EXIF orientation is
  applied. The original file is never altered.
- Uploaded images above **50 megapixels** are rejected before any derivative is made.

## Album Cover

- **Own cover**: an image stored on the album, independent of any photo.
- **Automatic**: when photos are uploaded into an album that, at that moment, has no live photos
  and no own cover, the first accepted photo becomes its cover (a resized copy — moving the photo
  later does not affect it).
- **Manual**: `PUT …/cover/` replaces it with any image; `DELETE …/cover/` removes it and
  nothing regenerates one.
- **Resolved cover** (read time, never stored): the album's own cover, otherwise the own cover of
  the first live descendant that has one, in tree order; a trashed album is never a source.
  `cover_source_album_id` names the album it comes from. No cover anywhere below: both
  `cover_url` and `cover_source_album_id` are `null`.
- Existing albums start without a cover.

---

## API Endpoints

| Method | Route                              | Permission | Purpose                                   |
|--------|------------------------------------|------------|-------------------------------------------|
| GET    | `/api/albums/`                     | member     | flat list of every album, tree order      |
| POST   | `/api/albums/`                     | manage     | create                                    |
| PATCH  | `/api/albums/{id}/`                | manage     | rename, move, `description`, `event_date` |
| PUT    | `/api/albums/order/`               | manage     | full order of one set of sibling albums   |
| PUT    | `/api/albums/{id}/cover/`          | manage     | upload own cover                          |
| DELETE | `/api/albums/{id}/cover/`          | owner      | remove own cover                          |
| GET    | `/api/photos/`                     | member     | every photo                               |
| POST   | `/api/photos/`                     | manage     | upload photos into an album               |
| PATCH  | `/api/photos/{id}/`                | manage     | edit metadata, move to another album      |
| GET    | `/api/albums/{id}/photos/`         | member     | photos directly in one album              |
| PUT    | `/api/albums/{id}/photos/order/`   | manage     | full order of the photos of one album     |
| DELETE | `/api/albums/{id}/`                | owner      | send the album and its subtree to trash   |
| DELETE | `/api/photos/{id}/`                | owner      | send the photo to the trash               |
| GET    | `/api/gallery/trash/`              | owner (override) | one entry per deletion batch        |
| POST   | `/api/gallery/trash/albums/{id}/restore/` | owner (override) | restore an album's batch     |
| POST   | `/api/gallery/trash/photos/{id}/restore/` | owner (override) | restore a photo deleted alone |
| GET    | `/api/gallery/changes/?since=`     | member     | change feed                               |
| PUT    | `/api/photos/{id}/members/`        | manage     | replace the tags of one photo             |
| POST   | `/api/photos/members/`             | manage     | add/remove tags on up to 200 photos       |
| GET    | `/api/gallery/taggable-members/`   | manage (override) | tag picker: every member, id and name |
| GET    | `/api/gallery/tagged-members/`     | member     | members tagged in a live photo, with count |

A nonexistent album or photo — in the route or referenced by `parent_id` / `album_id` in the
body — is `404` on every endpoint. A trashed item counts as nonexistent everywhere except the
trash endpoints, and so does anything placed under a trashed album. In an order request a
trashed id is reported in `unexpected`. Full request and response bodies:
`specs/013-gallery-write-api/contracts/gallery-api.md` and
`specs/014-gallery-trash-sync/contracts/gallery-trash-api.md` and
`specs/015-gallery-member-tags/contracts/gallery-tags-api.md`.

### GET /api/albums/

`200` with an array of Album resources, every live album including empty ones, in tree order.

### POST /api/albums/

Body: `name` (required), `parent_id` (optional, `null` = root), `description`, `event_date`.
`201` with the Album resource, placed last among its siblings. `400` for a blank name or a name
already used by a sibling.

### PATCH /api/albums/{id}/

Any subset of `name`, `parent_id` (`null` moves to root), `description`, `event_date` (`null`
clears). `200` with the Album resource. A move places the album last among its new siblings; the
same parent keeps its position. `400` for a duplicate sibling name, and for a cycle — the body
carries `album_id`, `parent_id` and `chain`.

### PUT /api/albums/order/

Body `{"parent_id": <id or null>, "ids": [...]}`. `204`. `400` when `ids` is not exactly the
current children of `parent_id`; the body carries `missing`, `unexpected`, `repeated`.

### PUT /api/albums/{id}/cover/ · DELETE /api/albums/{id}/cover/

`PUT`: multipart, one file in field `image`, validated like a photo upload; `200` with the Album
resource; on any validation failure `400` and the previous cover stays. `DELETE`: `204`, also
when there was no own cover; the file is removed after the change commits.

### GET /api/photos/

`200` with every live photo, ordered by the tree order of its album, then `position`, then `id`.

### GET /api/albums/{album_id}/photos/

`200` with the photos **directly** in the album (never those of sub-albums), by `position` then
`id`. `404` if the album does not exist; `200 []` for an existing empty album.

### Member filter (both photo lists)

`?member_id=1&member_id=2`: only the live photos tagged with **every** listed member (AND), in
the list's usual order; repeated values count once. A value that matches no member gives `[]`; a
value that is not an integer is `400` naming it. Without the parameter the lists are unchanged.

### POST /api/photos/

Multipart: `album_id` and one or more files in field `image`. The app sends one file per request;
several are accepted for tooling.

Each file is validated by `core.files.image_validation.detect_image_extension` (max 10 MB, must
decode as JPEG, PNG, WEBP or GIF), then the 50 MP limit, then the thumbnail is made. A failure at
any step rejects that file only, with its own reason, and nothing is kept for it.

| Outcome                    | Status | Body                                                           |
|----------------------------|--------|----------------------------------------------------------------|
| every file accepted        | `201`  | `{"accepted": [Photo…], "rejected": []}`                       |
| some accepted, some not    | `207`  | `{"accepted": [Photo…], "rejected": [{"filename", "reason"}]}` |
| every file rejected        | `400`  | canonical error `VALIDATION_ERROR`, detail "Nenhuma imagem foi aceita.", plus `rejected` |
| no `album_id` or no file   | `400`  | canonical error                                                |

An accepted photo gets `name` = the filename, empty `description`, `date_taken` from the EXIF
capture date (or `null`), the last position in the album, a thumbnail, and the uploader recorded.

### PATCH /api/photos/{id}/

Any subset of `name`, `description`, `date_taken` (`null` clears), `album_id`. Any other key —
the image included — is `400`. `200` with the Photo resource. A move places the photo last in the
target album; its files stay where they are.

### PUT /api/albums/{id}/photos/order/

Body `{"ids": [...]}`. `204`. Same exact-set rule and `400` body as album order.

### Album Resource

```json
{
  "id": 7,
  "name": "Retiro 2026",
  "parent_id": 2,
  "description": "",
  "event_date": "2026-03-14",
  "cover_url": "http://host/ipbcb/media/gallery/covers/9/3f2a….jpg",
  "cover_source_album_id": 9,
  "position": 3
}
```

### Photo Resource

```json
{
  "id": 1,
  "name": "IMG_0042.jpg",
  "description": "",
  "album_id": 7,
  "album_name": "Retiro 2026",
  "image_url": "http://host/ipbcb/media/gallery/7/9b1e….jpg",
  "thumbnail_url": "http://host/ipbcb/media/gallery/thumbs/7/c4d0….jpg",
  "date_taken": "2026-03-14",
  "uploaded_at": "2026-03-15T10:00:00Z",
  "position": 0,
  "members": [{"id": 12, "name": "Maria Souza"}]
}
```

`image_url`, `thumbnail_url` and `cover_url` are absolute URIs built from the request, `null`
when there is no file or no request. Every field returned before feature 013 is still returned;
`thumbnail_url` was added by 013, `position` by 014 and `members` (last field) by 015. `members`
lists the photo's tags as `{id, name}` — the only member data the gallery returns — ordered by
name then id, `[]` when untagged.

The files behind these URLs are readable only by members: `/ipbcb/media/gallery/...` goes
through the authenticated media access check (`specs/009-protected-media-access/`), which
requires the same `Profile.is_member` as the endpoints listing them. Holding the URL is not
enough — the request must carry the member's JWT. Covers and thumbnails live under `gallery/`
too, so the same rule covers them.

**Files of trashed items**: the original and thumbnail of a trashed photo (a photo trashed with
its album included) and the cover of a trashed album answer `404` to a member without `owner`
on `gallery`, from the moment of the delete, and stay readable to a user with `owner`. One
indexed lookup from the stored name to its row decides it; old paths
(`gallery/{slug}/{filename}`) are covered. A file that no row references keeps the plain member
rule. After the purge the file no longer exists.

---

## Trash

- `DELETE` sets `deleted_at`, the deletion batch and the actor; nothing leaves the database or
  the disk. Deleting an album trashes, in the same batch, its live descendants and every live
  photo in them; items already in the trash keep their own batch. Deleting a trashed or unknown
  item is `404`.
- `GET /api/gallery/trash/` lists one entry per batch, most recent first: `kind`, `id`, `name`,
  `deleted_at`, `deleted_by` and `uploaded_by` (display names or `null`), `purge_on`
  (`deleted_at` + 30 days), `sub_album_count`, `photo_count` and `thumbnail_url`. Items that went
  with an album entry are not listed on their own.
- Restore brings back exactly the batch of the entry, at the stored positions (ties by id), and
  nothing that was trashed under another batch. Only the entry's root can be restored: a live,
  purged or cascaded item is `404`. It is refused with `400` when the parent (or the photo's
  album) is in the trash, and, for an album, when a live sibling holds its name. The owner
  restores the parent, or renames the sibling, first; nothing is ever moved or renamed
  automatically.
- There is no manual permanent deletion; the purge is the only one.

## Purge

`python manage.py purge_gallery_trash`, run daily by a host cron on the production server
(`30 3 * * * docker exec ipbcb-server-prod python manage.py purge_gallery_trash`; this is its
record in this repository). It deletes, batch by batch in its own transaction, every batch
deleted more than 30 days ago: photos, then albums deepest first, then the batch row; the files
(`image`, `thumbnail`, `cover_image`) are removed after the commit, and a missing file is not an
error. A failing batch is skipped, reported and retried on the next run. Removing a row never
removes its deletion mark; the same run drops marks older than 90 days. Idempotent; exit code 0.

## Change Feed

`GET /api/gallery/changes/?since=<cursor>` returns `albums`, `photos` (the same resources as the
lists), `deleted_album_ids`, `deleted_photo_ids`, a new opaque `cursor` and
`full_sync_required`.

- Without `since`: every live item, empty deleted lists.
- With a cursor: items whose resource changed since 90 s before the cursor (the overlap that
  keeps a late commit from being missed; items may come twice), and ids deleted since then and
  not restored. "Changed" includes derived fields: every photo of a renamed album, every album
  whose resolved cover changed, every item whose `position` changed.
- A cursor older than 90 days, unreadable, from the future or of an unknown version: empty lists
  and `full_sync_required: true`; the app then reconciles against the two list endpoints.
- Every delete writes one mark per trashed row (kind, id, date), kept 90 days whether or not the
  row was purged; a restore removes the marks of what it brings back.
- A photo also counts as changed when its tags change (a tag write that changes nothing on it
  does not), and when a member tagged in it is renamed or deleted — through the members API or
  the Django admin. The last two reach the gallery through signal handlers on `Member`
  (`features/gallery/signals.py`, connected by the model's name, no import); only live photos are
  bumped, since a restore bumps a trashed one anyway.

## Tags

- `PUT /api/photos/{id}/members/` — body `{"member_ids": [...]}` replaces the photo's tags with
  exactly that set (`[]` clears); `200` with the Photo resource.
- `POST /api/photos/members/` — body `{"photo_ids": [...], "add_member_ids": [...],
  "remove_member_ids": [...]}` adds and removes only the listed pairs and keeps every other tag;
  `200` with the Photo resources in the order of `photo_ids`. At most **200** photos
  (`TAG_BULK_PHOTO_LIMIT`); `photo_ids` must not be empty, and at least one member list must not
  be; an id in both member lists is refused. These `400`s come before any database read.
- Both writes are atomic, under a lock of the live photo rows. Repeated ids count once. Any
  unknown or trashed photo, or unknown member, fails the whole request with one `404` listing
  every offending id (`missing_photo_ids`, `missing_member_ids`; trashed photos count as
  missing, as everywhere outside the trash). Only photos whose tags changed get a new
  `updated_at`.
- Each write that changed a tag logs one line, `gallery_tags_changed`, with `photo_ids`, `added`
  and `removed` (photo id → member ids) and `actor_id` — ids only.
- `GET /api/gallery/taggable-members/` — every member record, active or not, `[{id, name}]`
  ordered by name then id.
- `GET /api/gallery/tagged-members/` — every member tagged in at least one live photo,
  `[{id, name, photo_count}]` (live photos only) ordered by name then id.
- Both lists answer with `Cache-Control: private, no-store`, `Vary: Authorization` and an ETag.

---

## Errors

| Case                                   | Status | `error_code`       | Extra body fields                 |
|----------------------------------------|--------|--------------------|-----------------------------------|
| album / photo not found                | 404    | `NOT_FOUND`        |                                   |
| blank or duplicate sibling album name  | 400    | `VALIDATION_ERROR` |                                   |
| album moved under itself / descendant  | 400    | `VALIDATION_ERROR` | `album_id`, `parent_id`, `chain`  |
| order does not match the siblings      | 400    | `VALIDATION_ERROR` | `missing`, `unexpected`, `repeated` |
| every uploaded file rejected           | 400    | `VALIDATION_ERROR` | `rejected`                        |
| invalid cover image                    | 400    | `VALIDATION_ERROR` |                                   |
| no trash entry for the restored item   | 404    | `NOT_FOUND`        | `kind`, `id`                      |
| restore under a trashed parent         | 400    | `VALIDATION_ERROR` | `kind`, `id`, `trashed_parent_id` |
| restore onto a name a live sibling has | 400    | `VALIDATION_ERROR` | `album_id`, `name`, `conflicting_album_id` |
| tag write names a missing photo/member | 404    | `NOT_FOUND`        | `missing_photo_ids`, `missing_member_ids` |
| bulk tag write over 200 photos         | 400    | `VALIDATION_ERROR` | `photo_count`, `limit`            |
| member id in both bulk lists           | 400    | `VALIDATION_ERROR` | `member_ids`                      |
| empty bulk tag write                   | 400    | `VALIDATION_ERROR` |                                   |
| `member_id` filter not an integer      | 400    | `VALIDATION_ERROR` |                                   |

User-facing messages (duplicate name, cycle, image rejections, no image accepted, restore
refusals, tag refusals) are in
Portuguese; the order-mismatch and not-found messages address client developers and are in
English.

---

## Admin

Neither admin can delete an album or a photo (no delete button, no bulk action): deleting
happens in the app, where it is recorded, restorable and reported to devices. Trashed albums
and photos do not appear anywhere in the admin, including the album choices of the forms and
of the upload page.

### Album admin

Edits `name`, `parent`, `description`, `event_date`; `position` and `cover_image` are read-only.
The form validates through the same service as the API (duplicate sibling name, cycle) and saving
goes through it too, so a new or moved album is placed last among its siblings.

### Photo admin

Registered read-mostly: photos cannot be added from it (they arrive only through the upload
page, so every photo has a thumbnail); `image`, `thumbnail`, `uploaded_by` and `position` are
read-only. The page lists the photo's tagged members read-only; tags are changed only through
the API, so the feed and the log see every change.

### Upload page

Accessible at `/admin/gallery/album/upload/` (protected by Django admin login).

- **GET** renders an HTML form: album dropdown, multi-file image input (`image/*`), CSRF token.
- **POST** accepts `album` (ID) and `images` (file list) and calls the same upload service as
  `POST /api/photos/`, with the logged-in user as uploader — same validation, storage path,
  thumbnail, position and automatic cover.
- On full success: redirect to `admin:gallery_album_changelist`.
- On any rejection: re-render the form with one red message per rejected file,
  `"{filename}: {reason}"`; accepted files in the same batch are kept.

**Error messages (user-facing, Portuguese):**
- Missing album/files: "Selecione um álbum e ao menos uma imagem."
- Unknown album: "Álbum não encontrado."
- Per file: the reasons of `POST /api/photos/` (size and format come from
  `core.files.image_validation`, which is why they are in Portuguese: they reach the user
  verbatim).

---

## Management Commands

`python manage.py purge_gallery_trash` — see Purge.

`python manage.py generate_photo_thumbnails` — fills the thumbnail of every photo that has none.
Idempotent: a second run changes nothing. A photo whose original is missing or unreadable is
skipped and listed in the output; the others are still processed. Run once at the deploy of
feature 013.
