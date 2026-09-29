# Feature Specification: Gallery Write API

**Feature Branch**: `013-gallery-write-api`

**Created**: 2026-09-29

**Status**: Draft

**Input**: User description: "Add a write API for the gallery, nested albums, album covers,
per-photo thumbnails and manual ordering." (full request — current state, permissions, nested
albums, endpoint table, ordering, cover, thumbnail, upload, architecture and out-of-scope list —
in the `/speckit-specify` invocation that created this spec.)

## Context

Today the gallery is read-only over the API. Photos are uploaded through a Django admin HTML
form the Android app cannot use, and albums can only be created in the admin. The app derives
its album list and each album's cover from the photos it downloads (the `img00.jpg`
convention, else the first photo), so an empty album is invisible and there is no way to order
anything.

This feature gives the management panel of the app everything it needs to **build** the
gallery: create and nest albums, upload photos, edit their metadata, order albums and photos by
hand, and set album covers. It also makes the gallery lighter to browse: every photo gets a
server-made thumbnail, and every album gets a cover resolved by the server.

Feature 1 of 3. Deletion with a trash (014) and member tagging (015) are separate features.

### Relation to other specs

- **`specs/012-feature-role-permissions/`** — writes use scope `gallery`. This feature raises
  Liderança and Mídia from `manage` to `owner` on `gallery`, which amends 012 (FR-020 below).
- **`specs/009-protected-media-access/`** — every new file (originals, thumbnails, covers) lives
  under `gallery/`, already readable by members only. The media contract does not change.
- **`specs/gallery/spec.md`** — the domain spec; rewritten to the state this feature produces
  (FR-021).

## Clarifications

### Session 2026-09-29

- Q: Body of the upload `400` (every file rejected), given the constitution's canonical error
  shape? → A: canonical `{"error_code", "detail"}` plus a `rejected` list (Upload response).
- Q: Does the current app group photos by `album_name`, so non-unique names would merge
  albums? → A: No, it groups by `album_id`; no compatibility risk.
- Q: Pixel limit for uploads? → A: reject above 50 megapixels, per file (FR-016a).

## Definitions

### Album tree

An album has at most one parent album. Albums without a parent are **roots**. There is no depth
limit. An album may hold photos and sub-albums at the same time. The tree is never allowed to
contain a cycle.

### Siblings and order

- **Sibling albums**: albums with the same parent (roots are siblings of each other).
- **Photos of an album**: only the photos placed **directly** in it, never those of its
  sub-albums.
- Every album has a **position** among its siblings and every photo a **position** within its
  album. Reads order by position, then id. New or moved items go to the end.
- **Tree order**: depth-first, pre-order walk of the album tree, siblings visited by position
  then id.

### Cover resolution

An album's **own cover** is an image stored on the album itself, independent of any photo.
Its **resolved cover** is, at read time, its own cover if it has one, otherwise the own cover of
the first descendant that has one, in tree order. The **cover source** is the album the
resolved cover comes from. Nothing about inheritance is stored.

### Image derivatives

| Derivative | Shape | Format |
|------------|-------|--------|
| Album cover | 1000×1000 px square, center-cropped | JPEG, quality 85 |
| Photo thumbnail | longest side 1000 px, aspect ratio kept, no crop | JPEG, quality 85 |

Each size is a single constant so it can change later. Animated GIFs use their first frame.
The original photo file is never altered.

### Endpoints

| Method | Route | Level on `gallery` | Purpose |
|--------|-------|--------------------|---------|
| GET    | `/api/albums/` | member | flat list of every album |
| POST   | `/api/albums/` | manage | create an album |
| PATCH  | `/api/albums/{id}/` | manage | rename, move, edit `description` / `event_date` |
| PUT    | `/api/albums/order/` | manage | full new order of one set of sibling albums |
| PUT    | `/api/albums/{id}/cover/` | manage | upload a new own cover |
| DELETE | `/api/albums/{id}/cover/` | owner | remove the own cover |
| GET    | `/api/photos/` | member | *(existing)* every photo, in tree order |
| POST   | `/api/photos/` | manage | upload one or more photos into an album |
| PATCH  | `/api/photos/{id}/` | manage | edit `name`, `description`, `date_taken`; move to another album |
| GET    | `/api/albums/{id}/photos/` | member | *(existing)* photos directly in one album |
| PUT    | `/api/albums/{id}/photos/order/` | manage | full new order of the photos of one album |

"member" means the existing `IsMemberUser` permission, unchanged. Levels follow the method
defaults of 012; no endpoint overrides them.

### Album resource

```json
{
  "id": 7,
  "name": "Retiro 2026",
  "parent_id": 2,
  "description": "",
  "event_date": "2026-03-14",
  "cover_url": "http://host/ipbcb/media/gallery/covers/9/3f2a….jpg",
  "cover_source_album_id": 9
}
```

- `parent_id`: `null` for a root.
- `description`: may be empty; `event_date`: may be `null`.
- `cover_url`: absolute URI of the resolved cover, or `null`. `cover_source_album_id`: id of the
  cover source (the album itself when it has its own cover), or `null`. Both `null` together
  when no cover exists anywhere in the subtree; the app then shows black.

### Photo resource

The existing resource, with one field added:

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
  "uploaded_at": "2026-03-15T10:00:00Z"
}
```

`thumbnail_url` follows the `image_url` convention (absolute URI, `null` when there is no file or
no request). The uploader is never part of this resource.

### Upload response

For `POST /api/photos/` once the album is found and at least one file was sent:

| Outcome | Status | Body |
|---------|--------|------|
| every file accepted | `201` | `{"accepted": [...], "rejected": []}` |
| some accepted, some rejected | `207` | `{"accepted": [...], "rejected": [...]}` |
| every file rejected | `400` | canonical error plus `rejected` |

Success body:

```json
{
  "accepted": [ { "...": "photo resource" } ],
  "rejected": [ { "filename": "video.mp4", "reason": "Formato inválido: …" } ]
}
```

Every-file-rejected body — the canonical error shape of the constitution, extended with the
per-file list the same way validation errors already carry `field_errors`:

```json
{
  "error_code": "VALIDATION_ERROR",
  "detail": "Nenhuma imagem foi aceita.",
  "rejected": [ { "filename": "video.mp4", "reason": "Formato inválido: …" } ]
}
```

`reason` and `detail` are user-facing Portuguese. An error response is therefore always
canonical; the app switches on the status to know which shape to read.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Upload photos from the app (Priority: P1)

A person on the media team, after a church event, picks photos on their phone and sends them to
an album from the app's management panel, one per request. Each one appears for members in the
album, with a small thumbnail ready for the grid.

**Why this priority**: Uploading is the reason for the feature. Without it the app still depends
on someone at a computer with the Django admin.

**Independent Test**: As a Mídia user, upload a JPEG, a PNG and a text file renamed `.jpg` to an
existing album in one request; two are accepted with thumbnails, one is rejected with a reason,
status `207`; a member then lists the album and sees the two photos in upload order.

**Acceptance Scenarios**:

1. **Given** an existing album and a Mídia user, **When** they upload one valid JPEG, **Then**
   the answer is `201`, `accepted` holds one photo resource whose `name` is the original
   filename, with `image_url` and `thumbnail_url` set, and `rejected` is empty.
2. **Given** an upload of three files where one is not an image, **When** it is sent, **Then**
   the two images are stored, the third is listed in `rejected` with its filename and a
   Portuguese reason, and the status is `207`.
3. **Given** an upload where every file is invalid, **When** it is sent, **Then** nothing is
   stored, the status is `400`, and the body is the canonical error (`VALIDATION_ERROR`) with
   `rejected` listing every file and its reason.
4. **Given** a photo whose file carries an EXIF capture date, **When** it is uploaded, **Then**
   its `date_taken` is that date; **given** one without, `date_taken` is `null`.
5. **Given** an album already holding photos, **When** a photo is uploaded, **Then** it comes
   last in the album's order.
6. **Given** a file that passes format validation but cannot be turned into a thumbnail,
   **When** it is uploaded, **Then** it is rejected with its own reason and no photo record or
   original is kept for it.
7. **Given** a nonexistent album id, **When** an upload is sent, **Then** the answer is `404`
   and nothing is stored.
8. **Given** a member without any role, **When** they upload, **Then** the answer is `403`.
9. **Given** the Django admin upload page, **When** an administrator uploads there, **Then** the
   photos get the same storage path, thumbnail, position and uploader as an API upload.

---

### User Story 2 - Build the album tree (Priority: P1)

The media team creates albums from the app — a root "Retiros", then "Retiro 2026" inside it —
renames them, fills an optional description or event date, and moves an album under another.

**Why this priority**: Photos need a place to go, and today only the admin can create one.

**Independent Test**: Create a root, a child and a grandchild; rename the child; move the
grandchild to the root level; list albums and check `parent_id` of each; then try to move the
root under its own grandchild and get `400`.

**Acceptance Scenarios**:

1. **Given** a Liderança user, **When** they create an album with only a `name`, **Then** it is
   a root, last among roots, with empty `description`, `null` `event_date` and no cover.
2. **Given** an existing album, **When** a child is created with its `parent_id`, **Then** the
   child lists with that `parent_id` and is last among its siblings.
3. **Given** two roots, **When** a third root is created with the name of one of them, **Then**
   the answer is `400` and nothing is created. *(Regression: roots have no parent, and a
   uniqueness rule keyed on the parent alone misses them.)*
4. **Given** "2025" under "Retiros", **When** "2025" is created under "Acampamentos", **Then**
   it succeeds — names are unique only among siblings.
5. **Given** albums A → B → C (C inside B inside A), **When** A is moved under C, **Then** the
   answer is `400` with a message naming A and C, and the tree is unchanged. *(Regression.)*
6. **Given** album A, **When** A is moved under itself, **Then** the answer is `400`.
   *(Regression.)*
7. **Given** a child album, **When** it is moved with `parent_id: null`, **Then** it becomes a
   root, last among roots.
8. **Given** an album, **When** it is renamed or moved, **Then** no photo file, thumbnail or
   cover file changes path, and every URL returned before still works.
9. **Given** a nonexistent album id in the route, or a nonexistent `parent_id` in the body,
   **When** any album write is sent, **Then** the answer is `404`.

---

### User Story 3 - Members browse albums with covers (Priority: P1)

A member opens the gallery and sees every album, including empty ones and sub-albums, each with
a cover — its own, or one borrowed from a sub-album — without downloading every photo first.

**Why this priority**: The album list and covers are what make the new structure visible. It is
also the first read the app will switch to.

**Independent Test**: Build roots and sub-albums with and without covers; list albums as a
member and check each `cover_url` / `cover_source_album_id` against the resolution rule.

**Acceptance Scenarios**:

1. **Given** a member, **When** they list albums, **Then** every album is returned in one flat
   list, empty albums included, each with its `parent_id`.
2. **Given** an album with its own cover, **When** listed, **Then** its `cover_source_album_id`
   is its own id.
3. **Given** "Retiros" without a cover whose sub-albums, in order, are "2024" (no cover, but its
   own sub-album "Sábado" has one) and "2025" (has one), **When** listed, **Then** "Retiros"
   takes the cover of "Sábado" — depth-first, not breadth-first.
4. **Given** an album with no cover anywhere below it, **When** listed, **Then** `cover_url`
   and `cover_source_album_id` are both `null`.
5. **Given** a sub-album whose cover a parent inherits, **When** that cover is removed or
   replaced, **Then** the next list of the parent reflects it with no further action.
6. **Given** a user who is not a member, **When** they list albums, **Then** the answer is
   `403`.

---

### User Story 4 - Covers are set automatically and by hand (Priority: P2)

An album gets a cover on its own the moment its first photo arrives. Someone on the media team
can replace it with any image, even one that is not in the album, or remove it.

**Why this priority**: The automatic cover keeps most albums presentable with no effort; manual
control is a refinement.

**Independent Test**: Upload two photos into a new album; its cover is a square copy of the
first. Replace it with an unrelated image; remove it; upload another photo; the album stays
without a cover.

**Acceptance Scenarios**:

1. **Given** an album with no photos and no cover, **When** photos are uploaded into it,
   **Then** it gets a cover made from the first accepted photo.
2. **Given** that cover, **When** the photo it came from is moved to another album, **Then** the
   cover stays — it is a copy, not a link.
3. **Given** an album that already holds photos, **When** more are uploaded, **Then** the cover
   does not change.
4. **Given** a Mídia user, **When** they send an image to `PUT …/cover/`, **Then** it replaces
   the own cover, cropped to the square.
5. **Given** a `PUT …/cover/` with a file that is not a valid image, **When** it is sent,
   **Then** the answer is `400` and the previous cover stays.
6. **Given** an album with a cover, **When** a Mídia or Liderança user sends
   `DELETE …/cover/`, **Then** the album has no own cover and nothing regenerates one; its
   resolved cover falls back to its sub-albums, if any.
7. **Given** an album with no own cover, **When** `DELETE …/cover/` is sent, **Then** it
   succeeds and nothing changes.

---

### User Story 5 - Order albums and photos by hand (Priority: P2)

The media team puts "Retiro 2026" before "Retiro 2025", and the best photo first in the album.

**Why this priority**: Upload order is often wrong, and chronological-by-upload is the only
order today.

**Independent Test**: Send a full reversed order of the roots and of an album's photos; both
lists come back reversed. Send an order missing one id; `400`, nothing changes.

**Acceptance Scenarios**:

1. **Given** roots R1, R2, R3, **When** `PUT /api/albums/order/` is sent with `parent_id: null`
   and `ids: [R3, R1, R2]`, **Then** the album list orders roots R3, R1, R2.
2. **Given** an album with photos P1, P2, P3, **When** its photo order is set to `[P2, P3, P1]`,
   **Then** `GET /api/albums/{id}/photos/` returns them in that order.
3. **Given** a set of siblings, **When** the order request omits one id, adds an id from
   another parent, adds a nonexistent id, or repeats an id, **Then** the answer is `400` naming
   the offending ids, and no position changes.
4. **Given** new photos ordered by hand, **When** `GET /api/photos/` is read, **Then** photos
   come in tree order of their albums, then by position within each album.

---

### User Story 6 - Edit photo metadata and move photos (Priority: P2)

After the upload, someone writes a caption, fixes the date, renames a photo, or moves it to the
right album.

**Why this priority**: Upload creates metadata only from the file; captions come later.

**Independent Test**: PATCH a photo's description and album; it shows the caption and is listed
last in the new album, and its image URL is unchanged.

**Acceptance Scenarios**:

1. **Given** a photo, **When** `description`, `name` or `date_taken` is patched, **Then** only
   those fields change.
2. **Given** a photo in album A, **When** it is patched with `album_id` of B, **Then** it lists
   last in B, no longer in A, and its `image_url` and `thumbnail_url` are unchanged.
3. **Given** a PATCH that includes the image, **When** it is sent, **Then** the image is not
   changed (the field is not accepted).
4. **Given** a nonexistent photo id or a nonexistent `album_id`, **When** a PATCH is sent,
   **Then** the answer is `404`.

---

### User Story 7 - Existing photos get thumbnails at deploy (Priority: P3)

After the deploy, the operator runs one command once, and every photo uploaded before the
feature gets a thumbnail.

**Why this priority**: Only needed once, and until it runs the app still has the originals.

**Independent Test**: With photos lacking thumbnails, run the command twice; the first run
fills them all, the second changes nothing.

**Acceptance Scenarios**:

1. **Given** photos without a thumbnail, **When** the command runs, **Then** each gets one.
2. **Given** the command already ran, **When** it runs again, **Then** no thumbnail is
   regenerated.
3. **Given** a photo whose original is missing or unreadable, **When** the command runs,
   **Then** that photo is reported and skipped, and the others are still processed.
4. **Given** a photo without a thumbnail, **When** it is read before the command ran, **Then**
   its `thumbnail_url` is `null` and every other field is unchanged.

---

### Edge Cases

- **Old app versions.** Nothing is removed from the existing read endpoints. Photos uploaded
  after the deploy no longer carry their filename in `image_url` (the file is stored under a
  random name), but `name` keeps the original filename. Album names stop being globally
  unique; the current app groups photos by `album_id`, not `album_name`, so two albums named
  "2025" under different parents stay separate in it.
- **`GET /api/albums/{id}/photos/` for a nonexistent album** is now `404` (was `200 []`). An
  existing album with no photos still answers `200 []`.
- **Album name and whitespace.** Names are trimmed; a blank name is `400`. Uniqueness compares
  the trimmed name exactly (case-sensitive).
- **Rename to the same name** or **move to the current parent**: succeeds; the position does
  not change.
- **Order of an empty set** (an album with no photos, `ids: []`): succeeds, nothing changes.
- **Concurrent appends.** Two uploads into the same album at once may end with the same
  position; ties are broken by id, so the order stays deterministic and the next manual order
  rewrites positions cleanly.
- **Batch upload into an empty album** — the cover comes from the first *accepted* file, not
  the first file sent.
- **Automatic cover fails** after the photo itself was accepted: the photo stays accepted, the
  album stays without a cover, and the failure is logged.
- **Transparency** (PNG, WEBP, GIF) in a thumbnail or cover: flattened onto white, since JPEG
  has no alpha.
- **EXIF orientation**: thumbnails and covers are generated upright, following the orientation
  tag; the original file is left as uploaded.
- **Very large dimensions.** A file under 10 MB can still decode to an image too large for the
  server's memory. Photos and covers above 50 megapixels (width × height) are rejected with a
  per-file Portuguese reason, before any thumbnail or cover is generated. Phone cameras (12–48
  MP) pass.
- **Filename longer than the `name` limit**: `name` is cut to the limit, keeping the extension.
- **Photo moved between albums**: its files stay under the old album's folder. Paths carry the
  album id only to spread files; they are never read back to find the album.
- **Django admin edits.** Albums edited in the admin obey the same rules as the API: the admin
  cannot save a duplicate sibling name or a cycle. Cover resolution also stops at any album it
  already visited, so a cycle that reached the database by any path cannot hang a read.
- **Deleting an album in the Django admin** that has sub-albums is refused (deletion is feature
  014); one without sub-albums behaves as today.

## Requirements *(mandatory)*

### Functional Requirements

**Permissions**

- **FR-001**: Reads (`GET /api/albums/`, `GET /api/photos/`, `GET /api/albums/{id}/photos/`)
  MUST keep requiring membership (`IsMemberUser`) and nothing else.
- **FR-002**: Every write endpoint in the Endpoints table MUST declare scope `gallery` with the
  method's default level: `manage` for `POST`/`PUT`/`PATCH`, `owner` for `DELETE`.
- **FR-003**: Admin, Liderança and Mídia MUST all hold `owner` on `gallery` after the deploy,
  with no manual step. Liderança and Mídia are raised by a data migration whose reason is
  documented at the top of the file.

**Albums**

- **FR-004**: An album MUST have an optional parent album; existing albums MUST become roots.
- **FR-005**: An album name MUST be unique among its siblings, roots included, and this MUST
  hold for writes from the API and from the Django admin alike. A violation is `400`.
- **FR-006**: Moving an album under itself or under any of its descendants MUST be refused with
  `400` and a message naming the album being moved and the requested parent.
- **FR-007**: An album MUST have an optional `description` (default empty) and an optional
  `event_date` (default none).
- **FR-008**: `GET /api/albums/` MUST return every album as a flat list of Album resources, in
  tree order.

**Ordering**

- **FR-009**: Albums (among siblings) and photos (within their album) MUST have a position.
  Created, uploaded and moved items MUST be placed last. Existing rows MUST be backfilled:
  albums by name, photos by upload time.
- **FR-010**: Reads MUST order albums and photos by position, then id; `GET /api/photos/` MUST
  order by the tree order of the photo's album, then the photo's position.
- **FR-011**: An order request MUST carry the full new order. When `ids` is not exactly the set
  of current siblings — missing, extra, foreign, nonexistent or repeated ids — it MUST be
  refused with `400` naming the offending ids, and no position may change.

**Covers**

- **FR-012**: An album MUST be able to hold its own cover image, independent of any photo,
  stored as the square derivative under `gallery/covers/{album_id}/{random}.jpg`.
- **FR-013**: When photos are uploaded into an album that, at that moment, has no photos and no
  own cover, the album MUST get a cover made from the first accepted photo.
- **FR-014**: `PUT …/cover/` MUST accept one image, validated like a photo upload, and replace
  the own cover with its square derivative. `DELETE …/cover/` MUST remove the own cover and
  MUST NOT generate a new one.
- **FR-015**: The resolved cover and cover source MUST be computed at read time per the Cover
  resolution rule, never stored.

**Photos**

- **FR-016**: `POST /api/photos/` MUST accept an album id and one or more image files, validate
  each file with the existing gallery upload validation (10 MB, decoded content, JPEG / PNG /
  WEBP / GIF, per-file partial success) without rewriting it, and answer with the Upload
  response. Missing album id or no file is `400`. When every file is rejected, the `400` body
  MUST be the canonical error shape extended with `rejected`.
- **FR-016a**: A photo or cover image above 50 megapixels MUST be rejected with a per-file
  Portuguese reason before any derivative is generated. The limit is a single constant.
- **FR-017**: Each accepted photo MUST be stored at `gallery/{album_id}/{random}.{ext}`, with
  `ext` from the decoded format, `name` set to the original filename, `description` empty,
  `date_taken` from the EXIF capture date when present, and the uploading user recorded for
  auditing. Existing files MUST keep their paths.
- **FR-018**: Each accepted photo MUST get a thumbnail under
  `gallery/thumbs/{album_id}/{random}.jpg`. A file that cannot be thumbnailed MUST be rejected
  with its own reason, and nothing MUST be kept for it.
- **FR-019**: `PATCH /api/photos/{id}/` MUST accept only `name`, `description`, `date_taken` and
  `album_id`. It MUST never change the image, thumbnail or uploader.
- **FR-019a**: The Django admin upload page MUST stay, and MUST go through the same upload path
  as the API, so storage path, thumbnail, position, automatic cover and uploader are the same
  whichever way a photo arrives.
- **FR-019b**: A management command `generate_photo_thumbnails` MUST fill the thumbnail of every
  photo that lacks one, skipping and reporting photos whose original cannot be read. Running it
  twice MUST change nothing the second time.

**Errors**

- **FR-019c**: A nonexistent album or photo — in the route or referenced by `parent_id` /
  `album_id` in the body — MUST be `404`, on every endpoint.
- **FR-019d**: Cycle, duplicate sibling name, order mismatch and not-found MUST be domain
  exceptions with messages that include the offending value(s) and the expected shape.

**Specs**

- **FR-020**: `specs/012-feature-role-permissions/spec.md` MUST be amended: the scope matrix
  (`gallery`: Liderança and Mídia `owner`), the `gallery` future-feature note, FR-009 ("Leader
  MUST NOT hold `owner` on any scope"), SC-002 and User Story 2 ("Nothing they do can delete
  data"), and the "Leader + Media on `gallery` is `manage`" edge case — all of which state that
  Liderança never deletes.
- **FR-021**: `specs/gallery/spec.md` MUST describe the gallery as this feature leaves it,
  including the permission statement that still says Liderança and Mídia hold `manage`, in the
  same commit as the code.

### Key Entities

- **Album** (existing, extended): name unique among siblings; optional parent album; optional
  description and event date; position among siblings; optional own cover image.
- **Photo** (existing, extended): position within its album; thumbnail image; uploader
  (optional, set on upload, never shown to members; existing photos have none).
- **Resolved cover** (derived, not stored): the cover an album shows and the album it comes
  from.
- **Upload outcome**: per request, the accepted photos and, per rejected file, its filename and
  a Portuguese reason.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The media team can publish a photo from the app with no computer involved — 100%
  of gallery operations in scope (create, rename, move, order, upload, edit, set or remove a
  cover) are doable from the API.
- **SC-002**: A member opening the gallery sees every album, including empty ones, with the
  correct resolved cover, from a single album list plus the thumbnails on screen — no original
  photo needs to be downloaded to show the album grid.
- **SC-003**: 0 cycles and 0 duplicate sibling names can be created, through the API or the
  Django admin; each attempt is covered by an automated check.
- **SC-004**: 100% of photos uploaded after the deploy have a thumbnail; after the one-time
  command, 100% of readable pre-existing photos do too.
- **SC-005**: Renaming or moving any album or photo leaves 100% of previously returned image,
  thumbnail and cover URLs working.
- **SC-006**: An app version released before this feature keeps loading the gallery with no
  change to what it reads.
- **SC-007**: Admin, Liderança and Mídia can each perform every gallery write, including
  removing a cover; a user with no role performs none.

## Assumptions

- **Body references to missing albums are `404`**, not `400`, matching the existing upload
  (`NotFoundError` for an unknown album) and the "nonexistent album on any route is `404`" rule.
- **Tree order** (FR-008, FR-010) is the reading of "album path" in the request: the
  depth-first walk by position, the same walk cover resolution uses.
- **"First photo ever"** in the request is read as "at upload time the album has no photos and
  no own cover" (FR-013). An album emptied by moves and uploaded to again gets a cover only if
  it has no own cover — so a removed cover stays removed while the album keeps photos, but an
  emptied album can be re-covered by its next upload.
- **Transparency flattens onto white; orientation follows EXIF** in derivatives (Edge Cases).
- **Parent deletion is refused**, not cascaded, until feature 014 defines deletion. Photos keep
  their existing cascade.
- **Roles are seeded in `core` migrations** (`core/migrations/0005_seed_panel_roles.py`), so the
  migration raising Liderança and Mídia lives beside it, not in the gallery app.
- **The request size limit of nginx (30 MB) is not a constraint**: the app sends one photo per
  request; several files per request are for tooling.
- **Portuguese reasons** come from `core.files.image_validation` for validation failures; the
  thumbnail failure reason is a new Portuguese message owned by the image-processing interface.

## Out of Scope

- Deleting albums and photos, the trash, restoring, purging files, syncing deleted ids (014).
  `owner` is raised here only so `DELETE …/cover/` works and 014 needs no permission change.
- Tagging members in photos, `Profile.member` (015).
- Any Android app change, including its download strategy and dropping the `img00.jpg`
  convention.
- Reordering by anything other than a full ordered list of ids.
- A cover backfill for existing albums.
- Moving existing files to the new path scheme.
