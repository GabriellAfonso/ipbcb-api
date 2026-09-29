# Feature Specification: Gallery Trash and Change Feed

**Feature Branch**: `014-gallery-trash-sync`

**Created**: 2026-09-29

**Status**: Draft

**Input**: User description: "Add deletion to the gallery, done as a trash: deleting an album or a
photo hides it and starts a 30-day window in which it can be restored; after that it is purged for
good, files included. Also add a change feed so the Android app can learn what was created, edited
or deleted since its last sync, and remove deleted photos from the device as soon as it next
syncs." (full request — current state, deleting, trash, media access, purge, change feed,
permissions, observability, out-of-scope list and open decisions — in the `/speckit-specify`
invocation that created this spec.)

## Context

After feature 013 the media team can build the gallery from the app, but nothing can be taken out
of it. A photo sent to the wrong album, or one that should never have been published, stays
visible to every member. Worse, it stays on their phones: the app downloads every original once
and never learns that anything was removed, and any member holding the file's URL can keep
downloading it, because the media check of spec 009 decides by folder alone.

This feature adds deletion as a **trash**. Deleting hides the item at once — from every read, from
the file server and, on their next sync, from members' devices — but keeps it restorable for
**30 days**. After that it is purged for good, files included. It also adds a **change feed**, so
the app can fetch only what changed since its last sync, deletions included.

Feature 2 of 3. Member tagging in photos is feature 015.

### Relation to other specs

- **`specs/gallery/spec.md`** — the domain spec; rewritten to the state this feature produces
  (FR-040).
- **`specs/013-gallery-write-api/`** — the write API this feature extends. Its rules for sibling
  names, positions, tree order, the resolved cover and the automatic cover all start ignoring
  trashed items.
- **`specs/009-protected-media-access/`** — amended (FR-041). Until now a `gallery/` file is
  readable by any member, with no database lookup (009 FR-009, and the "orphan files" edge case).
  From this feature on, a file of a trashed item is not.
- **`specs/012-feature-role-permissions/`** — amended (FR-042): the trash, restore and change
  endpoints join its endpoint classification. No role changes; Admin, Liderança and Mídia already
  hold `owner` on `gallery` since 013.
- **`specs/002-structured-json-logging/`** — delete, restore and purge are logged in its format.
- **`specs/001-api-error-handling/`** — every refusal uses its canonical error shape.

## Clarifications

### Session 2026-09-29

- Q: Restoring an album while a live sibling holds its name? → A: refuse with a domain error
  naming the album and the conflicting sibling; the owner renames the sibling first. No name is
  ever invented (FR-021).
- Q: Restoring a photo whose album is in the trash, or an album whose parent is? → A: refuse,
  naming the trashed parent; the owner restores it first, from the same trash listing (FR-022).
- Q: Manual permanent deletion (purge one entry, empty the trash)? → A: no. The 30-day purge is
  the only permanent deletion; the window is the safety net for the three roles holding `owner`
  (FR-025, Out of Scope).
- Q: Order in the feed, given that neither resource carries its position? → A: add `position`
  to the Album and Photo resources, additively, on every endpoint that returns them (FR-039a).
- Q: Files under `gallery/` that no row references? → A: keep spec 009's behaviour, readable by
  members. A `404` could hide a live photo whose stored name does not match its URL exactly,
  which is worse than the old admin deletions it would close. A command that only lists orphans
  may come later, outside 014 (Assumptions).
- Q: Is FR-034 (derived fields count as changes) more than asked? → A: no, it is the rule: the
  feed returns what the app would see differently, not only rows that were written. The
  mechanism is the plan's decision.
- Q (planning): How does the feed avoid missing a change that commits after a read started? →
  A: an overlap. Each read re-covers the 90 s before its cursor, so items changed then may come
  again. The app applies the feed idempotently. The alternative, a 90 s delay before a change
  shows up, was rejected (SC-006, US3-2).
- Q (planning): Admin deletion, through the trash or not offered? → A: not offered. The app is
  the deletion UI (FR-012).
- Planning note: "the purge never removes deletion marks" means removing a row never removes
  its mark. The same daily command drops marks older than the mark retention, in a separate
  step (FR-033).

## Definitions

### Trash

An album or photo is **in the trash** (trashed) from the moment it is deleted until it is restored
or purged. A trashed item is not part of the gallery: no ordinary read returns it, no rule of the
gallery counts it, and members cannot fetch its files. Only users holding `owner` on `gallery`
see it, through the trash endpoints. An item that is not trashed is **live**.

### Deletion batch

Everything one delete action sends to the trash shares one **deletion batch**. Deleting a photo
makes a batch of one photo. Deleting an album makes a batch of the album, every live descendant
album and every live photo in any of them. Items that were already in the trash when the album was
deleted keep their own, older batch. Restoring an album restores its batch, exactly.

### Trash entry

What the trash listing shows: one entry per deletion batch, named after the item the action was
taken on — the **batch root**. A batch rooted at an album is one album entry, with the counts of
the sub-albums and photos that went with it; its members are never listed separately.

### Retention

| What | Kept for | Counted from |
|------|----------|--------------|
| Trashed album or photo, with its files | 30 days (**trash retention**) | the deletion |
| Deletion mark of the change feed | 90 days (**mark retention**) | the deletion |

Each retention is a single constant. Mark retention is independent of the trash: purging an item
never removes its mark, so an id keeps appearing as deleted in the feed after its row is gone.

### Change feed

A read that returns, relative to a **cursor** the server issued on a previous read, the albums and
photos that were created or changed and the ids of those that were deleted. The cursor is opaque
to the app: it stores it and sends it back, and never builds or parses one.

### Endpoints

| Method | Route | Permission | Purpose |
|--------|-------|------------|---------|
| DELETE | `/api/albums/{id}/` | `owner` on `gallery` (method default) | send an album and its subtree to the trash |
| DELETE | `/api/photos/{id}/` | `owner` on `gallery` (method default) | send a photo to the trash |
| GET    | `/api/gallery/trash/` | `owner` on `gallery` (override, above `view`) | list the trash entries |
| POST   | `/api/gallery/trash/albums/{id}/restore/` | `owner` on `gallery` (override, above `manage`) | restore an album's batch |
| POST   | `/api/gallery/trash/photos/{id}/restore/` | `owner` on `gallery` (override, above `manage`) | restore a photo deleted on its own |
| GET    | `/api/gallery/changes/?since=<cursor>` | member (`IsMemberUser`) | change feed |

Every endpoint of 013 is unchanged in route and permission.

### Trash entry resource

```json
{
  "kind": "album",
  "id": 7,
  "name": "Retiro 2026",
  "deleted_at": "2026-09-29T14:03:11Z",
  "deleted_by": "Maria Souza",
  "uploaded_by": null,
  "purge_on": "2026-10-29",
  "sub_album_count": 2,
  "photo_count": 41,
  "thumbnail_url": "http://host/ipbcb/media/gallery/covers/7/3f2a….jpg"
}
```

- `kind`: `album` or `photo`.
- `deleted_by` / `uploaded_by`: the user's display name, or `null` when the user no longer exists
  (and always `null` for `uploaded_by` of an album or of a photo uploaded before 013).
- `purge_on`: the date the entry becomes eligible for purge (`deleted_at` + trash retention).
- `sub_album_count` and `photo_count`: for an album entry, how many descendant albums and photos
  its batch holds; `0` for a photo entry.
- `thumbnail_url`: the photo's thumbnail, or the album's own cover; `null` when there is none.
  Readable by the caller because they hold `owner` (FR-030).

The listing is ordered by `deleted_at`, most recent first, then by id.

### Change feed response

```json
{
  "albums": [ { "...": "album resource" } ],
  "photos": [ { "...": "photo resource" } ],
  "deleted_album_ids": [12, 13],
  "deleted_photo_ids": [301, 302, 305],
  "cursor": "opaque-string",
  "full_sync_required": false
}
```

`albums` and `photos` hold the Album and Photo resources exactly as `GET /api/albums/` and
`GET /api/photos/` return them.

### Album and Photo resources

Both keep every field of 013 and gain one: `position` (integer), the album's position among its
siblings or the photo's within its album. Everywhere they are returned — the list endpoints, the
013 write responses, the restore response and the feed.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Delete a photo sent by mistake (Priority: P1)

Someone on the media team uploads a photo that should not be public — the wrong album, a blurry
shot, a person who asked not to appear. They delete it from the app. It disappears for everyone at
once, and nobody can download it any more, even with the link.

**Why this priority**: This is the reason for the feature. Today a mistaken upload can only be
removed by someone at a computer, and even then its file stays downloadable.

**Independent Test**: As Mídia, delete a photo; as a member, list the album and all photos (it is
gone) and request its original and thumbnail URLs (both `404`); as an owner, request the same URLs
(served).

**Acceptance Scenarios**:

1. **Given** a live photo and a Mídia user, **When** they send `DELETE /api/photos/{id}/`,
   **Then** the answer is `204`, and the photo is absent from `GET /api/photos/` and from
   `GET /api/albums/{album_id}/photos/`.
2. **Given** that trashed photo, **When** a member requests its original or its thumbnail through
   the media URL, **Then** the answer is `404`, from the first request after the delete.
3. **Given** the same files, **When** a user holding `owner` on `gallery` requests them, **Then**
   they are served.
4. **Given** a photo already in the trash, **When** it is deleted again, **Then** the answer is
   `404` and nothing changes.
5. **Given** a member without any role, **When** they delete a photo, **Then** the answer is
   `403`, whether or not the photo exists.
6. **Given** a trashed photo, **When** anyone sends `PATCH /api/photos/{id}/`, or includes its id
   in a photo order request, **Then** it is treated as nonexistent (`404`, or an order mismatch
   naming it).
7. **Given** a deletion, **When** it completes, **Then** nothing is removed from the database or
   from the disk.

---

### User Story 2 - Delete an album and everything under it (Priority: P1)

The media team deletes "Retiro 2025", which holds two sub-albums and forty photos. Everything
under it goes to the trash in the same action, and nothing of it remains visible anywhere.

**Why this priority**: Without a cascade, deleting a filled album would mean deleting every photo
and every sub-album by hand, bottom-up — today it is simply impossible.

**Independent Test**: Build A → B → C with photos at each level; delete A; list albums and photos
as a member (none of A, B, C or their photos); check the cover of A's parent and the name reuse.

**Acceptance Scenarios**:

1. **Given** album A with sub-album B, B with sub-album C, and photos in all three, **When** A is
   deleted, **Then** A, B, C and every photo in them are trashed in one deletion batch, and none
   of them appears in `GET /api/albums/` or `GET /api/photos/`.
2. **Given** that A is trashed, **When** `GET /api/albums/{A}/photos/` or
   `GET /api/albums/{B}/photos/` is read, **Then** the answer is `404`.
3. **Given** a parent P whose resolved cover came from B, **When** A is deleted, **Then** P's
   resolved cover falls to the next live descendant with its own cover, or to `null`; a trashed
   album is never a cover source.
4. **Given** that A named "Culto" was trashed under P, **When** a new album "Culto" is created
   under P, **Then** it succeeds.
5. **Given** a trashed album, **When** anyone creates an album under it, moves an album or a photo
   into it, uploads photos into it, sets or removes its cover, renames it, reorders its children
   or its photos, or deletes it again, **Then** the answer is `404`.
6. **Given** an album whose only photos are in the trash, **When** a photo is uploaded into it and
   it has no own cover, **Then** it gets the automatic cover, as an album with no photos does.
7. **Given** a photo trashed on its own before its album was deleted, **When** the album is
   deleted, **Then** that photo keeps its own, older batch and is not counted in the album's
   entry.

---

### User Story 3 - The app forgets what was deleted (Priority: P1)

A member's phone holds every photo of the gallery. When the app next syncs, it asks the server
what changed since its last sync, receives the ids of what was deleted, and removes those photos
from the device.

**Why this priority**: Hiding a photo on the server is not enough while copies stay on every
phone. The feed is also what lets the app stop downloading the whole gallery on every sync.

**Independent Test**: Sync once without a cursor; create an album, edit a photo, delete another
photo and an album with photos; sync with the cursor and check each list.

**Acceptance Scenarios**:

1. **Given** a member and no cursor, **When** they read `GET /api/gallery/changes/`, **Then** the
   answer holds every live album and photo, empty deleted lists, a cursor, and
   `full_sync_required: false`.
2. **Given** that cursor, **When** an album is created, a photo is renamed, and the member reads
   the feed with it, **Then** `albums` holds the new album, `photos` holds the renamed photo, and
   nothing that last changed more than 90 s before the cursor is returned.
3. **Given** a cursor, **When** a photo is deleted on its own, **Then** the next feed read lists
   its id in `deleted_photo_ids`.
4. **Given** a cursor, **When** an album with a sub-album and photos is deleted, **Then** the next
   feed read lists both albums in `deleted_album_ids` and every one of their photos in
   `deleted_photo_ids`.
5. **Given** a deletion 40 days ago, after its item was purged, **When** a member reads the feed
   with a cursor from before the deletion, **Then** the id is still in the deleted list.
   *(Regression: the mark outlives the row.)*
6. **Given** a cursor older than the mark retention, **When** it is sent, **Then** the answer is
   `full_sync_required: true` with a new cursor, and the app reconciles against
   `GET /api/albums/` and `GET /api/photos/`.
7. **Given** a cursor, **When** a trashed item is restored, **Then** the next feed read returns it
   in `albums` or `photos` and no longer lists its id as deleted.
8. **Given** a user who is not a member, **When** they read the feed, **Then** the answer is
   `403`.
9. **Given** an app version released before this feature, **When** it reads `GET /api/albums/`
   and `GET /api/photos/`, **Then** every field it read before is still there, with the same
   meaning; only trashed items are missing and `position` is added.
10. **Given** a cursor, **When** the photos of an album are reordered, **Then** the next feed
    read returns every photo whose position changed, each with its new `position`, and no other.
11. **Given** a cursor, **When** album A is renamed, **Then** the next feed read returns A and
    every photo in A (their `album_name` changed); **when** a sub-album's own cover is replaced,
    **Then** it returns that sub-album and every ancestor whose resolved cover changed.

---

### User Story 4 - Restore something deleted by mistake (Priority: P2)

Someone deleted the wrong album. An owner opens the trash, sees the album with the number of
sub-albums and photos that went with it, and restores it. Everything comes back as it was — and
nothing that was already in the trash before comes back with it.

**Why this priority**: The trash is the safety net that makes giving `owner` to three roles
acceptable. Deleting has to work first.

**Independent Test**: Trash a photo P1 of album A; then delete A (batch with sub-album B and
photos P2, P3); restore A; A, B, P2, P3 are live in their old positions, P1 is still in the trash.

**Acceptance Scenarios**:

1. **Given** the trash holds album A (with sub-album B and photos P2, P3) and photo P1 trashed
   before A, **When** an owner reads `GET /api/gallery/trash/`, **Then** it lists two entries:
   album A with `sub_album_count: 1` and `photo_count: 2`, and photo P1; B, P2 and P3 are not
   listed on their own.
2. **Given** each entry, **When** it is listed, **Then** it carries its kind, id, name, deletion
   time, who deleted it, who uploaded it (photos), the purge date, and a thumbnail when there is
   one.
3. **Given** that trash, **When** A is restored, **Then** A, B, P2 and P3 are live again, each at
   its stored position (ties by id), and P1 is still in the trash.
4. **Given** a restored album, **When** members list albums, **Then** it is back under its
   parent, and the parent's resolved cover can come from it again.
5. **Given** an album or photo that is live, or that was purged, or that is in the trash only as a
   member of another item's batch (for instance B while A is trashed), **When** its restore is
   requested, **Then** the answer is `404`.
6. **Given** a Mídia or Liderança user, **When** they read the trash or restore an entry, **Then**
   it succeeds; **given** a member without a role, **Then** the answer is `403`.
7. **Given** album "Culto" trashed under P and a new live "Culto" created under P, **When** the
   trashed one is restored, **Then** the answer is `400` naming the album, the name and the live
   sibling's id, and nothing is restored; **when** the live sibling is renamed and the restore is
   sent again, **Then** it succeeds.
8. **Given** photo P1 trashed on its own and then its album A trashed, **When** P1 is restored,
   **Then** the answer is `400` naming P1 and A, and P1 stays in the trash; **when** A is
   restored first, **Then** restoring P1 succeeds. The same holds for an album whose parent is
   trashed.
9. **Given** an owner, **When** they look for a way to delete a trash entry for good, **Then**
   there is none: only the purge removes it (FR-025).

---

### User Story 5 - The trash empties itself after 30 days (Priority: P2)

Every day the operator's scheduled job purges whatever has been in the trash for more than 30
days, rows and files, so deleted photos do not stay on the server forever.

**Why this priority**: Without the purge the trash only hides; storage keeps growing and removed
photos still exist. It can ship a little after deletion without harm, since nothing is lost while
it waits.

**Independent Test**: Trash an album tree and a single photo, move their deletion 31 days back,
run the purge twice; rows and files are gone after the first run, the second changes nothing, and
the feed still lists the ids as deleted.

**Acceptance Scenarios**:

1. **Given** trashed items deleted more than 30 days ago, **When** the purge runs, **Then** their
   rows and their original, thumbnail and cover files are deleted for good.
2. **Given** trashed items deleted less than 30 days ago, **When** the purge runs, **Then** they
   are untouched.
3. **Given** a trashed album tree A → B → C, **When** it is purged, **Then** it succeeds even
   though an album cannot be deleted while it has sub-albums: descendants go first.
   *(Regression.)*
4. **Given** a purge that already ran, **When** it runs again, **Then** nothing changes and
   nothing fails.
5. **Given** a trashed photo whose file is already missing from disk, **When** it is purged,
   **Then** its row is deleted and the run does not fail.
6. **Given** one item whose purge fails, **When** the purge runs, **Then** every other eligible
   item is still purged, and the run reports what it purged and what it skipped.
7. **Given** the database step of a purge fails, **When** the run ends, **Then** no file of that
   item has been removed from disk.

---

### User Story 6 - The Django admin cannot bypass the trash (Priority: P3)

An administrator who opens an album or a photo in the Django admin finds no way to delete it.
Deleting happens in the app, where it is recorded, restorable and reported to devices. Today the
admin removes the row and leaves its files on disk.

**Why this priority**: The admin is rarely used for this now that the app can delete, but a single
bypass leaves orphaned files and deletions the feed never reports.

**Independent Test**: Open an album and a photo in the admin, and the changelists; there is no
delete button and no bulk delete action; a direct POST to the delete URL is refused.

**Acceptance Scenarios**:

1. **Given** the Django admin, **When** an album or photo page or changelist is shown, **Then**
   it offers no delete, single or bulk, and the admin delete URL is refused.
2. **Given** the admin album list, the album parent field and the upload page's album choice,
   **When** they are shown, **Then** no trashed album is offered.

---

### Edge Cases

- **Delete races an upload.** An upload into an album, or a move into it, that commits while the
  album is being deleted must not leave a live photo or album under a trashed album: either it
  lands before the delete and is trashed with the batch, or it is refused with `404`.
- **Delete races a feed read.** A change that commits while a feed read runs is returned by that
  read or by the next one, never by neither.
- **Order endpoints after a delete.** The sibling set of an order request counts live items only.
  An id of a trashed item in `ids` is reported as nonexistent, like any unknown id.
- **Positions after a restore.** A restored item keeps the position it had. It may equal a live
  sibling's; ties are broken by id, as in 013, and the next manual order rewrites positions.
- **Descendants of a restored album.** While an album is trashed, nothing can be added under it
  (every write under a trashed album is `404`), so its descendants can have no name conflict on
  restore; only the batch root can.
- **Cover of a trashed descendant.** It is never inherited. When the descendant is restored, it
  becomes a possible cover source again with no other action.
- **An emptied album and the automatic cover.** Trashed photos do not count: an album whose photos
  are all trashed counts as having no photos for the 013 automatic cover rule.
- **Purge order with separate batches.** A sub-album trashed on its own before its parent was
  deleted is purged before its parent, since its deletion is older. A live item never sits under a
  trashed album, so a purged album never holds a live descendant.
- **Purge day.** The purge date is a lower bound: an item is purged on the first purge run after
  its trash retention ends, so a daily run removes it within a day of `purge_on`.
- **Feed without changes.** A read with a cursor and no change since returns empty lists and a
  cursor the app can keep using.
- **Malformed cursor.** A cursor the server cannot read is answered like an expired one:
  `full_sync_required: true` with a fresh cursor, never an error that would block the app's sync
  for good.
- **Rename and derived fields.** Renaming an album changes the `album_name` of every photo in it;
  replacing, removing, trashing or restoring a cover can change the resolved cover of every
  ancestor. Each of those photos and albums counts as changed in the feed (FR-034).
- **Owner who is not a member.** A user holding `owner` on `gallery` but not flagged a member can
  read the files of trashed items (for the trash) while the files of live items keep requiring
  membership, as 009 defines. Their account is misconfigured, not the rule.
- **Files not referenced by any row.** Files left on disk by deletions made in the Django admin
  before this feature have no row. See Assumptions (orphan files).
- **Trashed items and old app versions.** An app that does not read the feed keeps the photo on
  the device; the file stops being downloadable for it too, since the media rule applies to every
  client.

## Requirements *(mandatory)*

### Functional Requirements

**Deleting**

- **FR-001**: `DELETE /api/albums/{id}/` and `DELETE /api/photos/{id}/` MUST require `owner` on
  `gallery` (the method's default level) and answer `204`.
- **FR-002**: A delete MUST be soft: it records when (UTC) and by whom the item was deleted and
  its deletion batch, and it removes nothing from the database or the disk.
- **FR-003**: Deleting an album MUST trash, in the same action and batch, the album, every live
  descendant album and every live photo in any of them. Items already in the trash keep their
  batch.
- **FR-004**: Deleting an item that is already in the trash, or that does not exist, MUST be
  `404`.
- **FR-005**: Every delete MUST write a deletion mark (FR-035) for each album and photo it
  trashes.

**Invisibility**

- **FR-006**: No ordinary read may return a trashed item: `GET /api/albums/`, `GET /api/photos/`,
  `GET /api/albums/{id}/photos/` and the live lists of the change feed.
- **FR-007**: A trashed album or photo MUST be treated as nonexistent (`404`) by every 013 write
  that names it in the route or the body, and by every write that would place something under a
  trashed album.
- **FR-008**: A trashed album MUST never be a cover source; the resolved cover skips it and its
  subtree.
- **FR-009**: The 013 automatic-cover condition ("the album has no photos") MUST count live photos
  only.
- **FR-010**: Album name uniqueness among siblings MUST consider live albums only, on every path
  that enforces it (API and Django admin).
- **FR-011**: The sibling set of an order request MUST contain live items only.
- **FR-012**: The Django admin MUST NOT delete an album or photo row: it offers no delete, single
  or bulk, and the app is the only place to delete (clarified). The
  admin album list, parent choice and upload page album choice MUST NOT offer trashed albums.

**Trash**

- **FR-013**: `GET /api/gallery/trash/` MUST require `owner` on `gallery`, declared as an override
  above the `GET` default (spec 012), and return one Trash entry resource per deletion batch
  still in the trash, ordered by `deleted_at` descending, then id.
- **FR-014**: A batch rooted at an album MUST be listed as one album entry carrying the counts of
  its descendant albums and photos; its members MUST NOT be listed on their own.
- **FR-015**: The trash MUST show the uploader of a photo to owners; the Photo resource of members
  still never carries it (013).

**Restore**

- **FR-016**: `POST /api/gallery/trash/albums/{id}/restore/` and
  `POST /api/gallery/trash/photos/{id}/restore/` MUST require `owner` on `gallery`, declared as an
  override, and answer `200` with the restored Album or Photo resource.
- **FR-017**: Restoring an album MUST make live exactly the items of its batch, and nothing that
  was in the trash under another batch.
- **FR-018**: A restored item MUST keep its stored parent or album and its stored position; ties
  are broken by id.
- **FR-019**: Restoring an item that is live, purged, nonexistent, or not a batch root, MUST be
  `404`.
- **FR-020**: Restoring MUST remove the deletion marks of every item it makes live, and those
  items MUST appear as changed in the feed (FR-034).
- **FR-021**: When an album is restored while a live sibling holds its name, the restore MUST be
  refused with `400` (`VALIDATION_ERROR`), naming the album being restored, its name, and the id
  of the conflicting sibling. Nothing of the batch is restored. The system never renames either
  album.
- **FR-022**: When a photo is restored while its album is in the trash, or an album while its
  parent is, the restore MUST be refused with `400` (`VALIDATION_ERROR`), naming the item and
  the trashed parent album, so the owner restores the parent first. Nothing is restored, and the
  item is never moved.
- **FR-023**: Every restore refusal MUST be a domain exception in the canonical error shape
  (spec 001), with a message that names the offending values and the expected state.

**Permanent deletion**

- **FR-025**: The purge of FR-031 MUST be the only way an album or photo is deleted for good. No
  endpoint purges a trash entry early or empties the trash.

**Media access (amends spec 009)**

- **FR-024**: A file under `gallery/` that is the original, thumbnail or cover of a trashed item
  MUST be answered `404` to a caller without `owner` on `gallery`, from the moment the delete
  commits. This covers a trashed photo, a photo trashed with its album, and a trashed album's
  own cover.
- **FR-026**: The same files MUST stay readable to a caller holding `owner` on `gallery`.
- **FR-027**: Deciding FR-024 MUST cost at most one indexed database lookup per media request,
  from the stored file name to its row, and MUST cover the paths of photos uploaded before 013
  (`gallery/{slug}/{filename}`).
- **FR-028**: The response for any file outside `gallery/` MUST NOT change, and the order of
  checks of spec 009 (authentication, path validation, folder rule, permission, existence) MUST
  be kept, with the trash check after the folder rule and before existence.
- **FR-029**: A purged item's files no longer exist, so the ordinary `404` of spec 009 applies.
- **FR-030**: The thumbnail and cover URLs of the trash listing MUST be served to the owner who
  reads them (a consequence of FR-026, stated so a test pins it).

**Purge**

- **FR-031**: A management command `purge_gallery_trash` MUST delete for good every trashed album
  and photo whose deletion is older than the trash retention, together with its original,
  thumbnail and cover files. The retention is one constant (30 days).
- **FR-032**: The purge MUST delete descendant albums before their parents, since an album with
  sub-albums cannot be deleted; it MUST be idempotent and safe to run daily.
- **FR-033**: Files MUST be removed only after the database change that purged their row has
  committed; a file already missing MUST NOT be an error; one failing item MUST NOT stop the run;
  the command MUST report what it purged and what it skipped. Removing a row MUST NOT remove its
  deletion mark; the same command drops marks older than the mark retention, in a separate step.

**Change feed**

- **FR-034**: Albums and photos MUST record when they last changed. Every change to any field of
  their resource MUST count, including a cover change, a move, a rename, a reorder, a restore, and
  the derived fields: an album's resolved cover changing because a descendant's cover or
  presence changed, and a photo's `album_name` changing because its album was renamed.
- **FR-035**: Every deletion MUST record a mark holding only the kind, the id and the deletion
  time. Marks MUST be kept for the mark retention (90 days, one constant) from the deletion,
  whether or not the item has been purged, and removed when the item is restored.
- **FR-036**: `GET /api/gallery/changes/` MUST require membership (`IsMemberUser`) and answer the
  Change feed response:
  - without `since`: every live album and photo, empty deleted lists,
    `full_sync_required: false`;
  - with a valid `since` within the mark retention: the live albums and photos created or changed
    after it, the ids of albums and photos deleted after it and not restored since,
    `full_sync_required: false`;
  - with a `since` older than the mark retention, or unreadable: empty lists,
    `full_sync_required: true`.
  Every answer carries a new cursor.
- **FR-037**: `deleted_photo_ids` MUST include photos trashed because their album was deleted.
- **FR-038**: No change committed concurrently with a feed read may be missed by both that read
  and the next one made with the cursor it returned.
- **FR-039**: `GET /api/albums/`, `GET /api/photos/` and `GET /api/albums/{id}/photos/` MUST
  keep their shape; nothing is removed from any existing response.
- **FR-039a**: The Album and Photo resources MUST gain `position` (the album's position among its
  siblings, the photo's position within its album), on every endpoint that returns them, the feed
  included. Additive only. A reorder counts as a change (FR-034) for every item whose position
  changed, so a delta carries the new order on its own.

**Specs**

- **FR-040**: `specs/gallery/spec.md` MUST describe the gallery as this feature leaves it —
  deletion, trash, restore, purge, change feed, the media rule, `position` in both resources,
  and the removal of "Deletion as a
  feature belongs to feature 014" — in the same commit as the code.
- **FR-041**: `specs/009-protected-media-access/spec.md` MUST be amended: FR-005's `gallery` row,
  FR-009 ("Access MUST NOT depend on any database record"), the "orphan files" edge case and the
  "No database lookup" assumption, all of which this feature changes for `gallery/`.
- **FR-042**: `specs/012-feature-role-permissions/spec.md` MUST list the gallery endpoints of this
  feature in its Endpoint Classification — `DELETE` on albums and photos at the default `owner`,
  the trash read and the two restores as `owner` overrides — and state that the change feed is a
  member endpoint outside the classification.

**Observability and architecture**

- **FR-043**: Each delete, restore and purged trash entry MUST write one structured JSON log line
  (spec 002) with the kind, id, batch, actor (`null` for the purge) and the counts of albums and
  photos affected. The purge run also logs one line per skipped item and a summary line.
- **FR-044**: Deletion, restore, purge and the feed MUST follow the project layering, with
  business rules outside the views and refusals as domain exceptions, and a regression test for
  each of: cascade and exact batch restore, name reuse after a delete, invisibility in every read
  of FR-006 to FR-009, the media rule for a member and for an owner, purge order with sub-albums,
  and the change feed across a purge.

### Key Entities

- **Album** (existing, extended): when it was deleted and by whom, its deletion batch (all empty
  while live), and when it last changed.
- **Photo** (existing, extended): same four attributes as Album.
- **Deletion batch**: the set of items one delete action trashed, identified so a restore brings
  back exactly that set; its root is the item the action was taken on.
- **Deletion mark**: kind (album or photo), id and deletion time of a deleted item. Independent of
  the item's row: it survives the purge and lives for the mark retention.
- **Trash entry** (derived, not stored): one batch as the owner sees it — its root, counts, who
  and when, and its purge date.
- **Feed cursor** (issued, opaque): the point in the gallery's history a client has synced up to.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A deleted photo stops being viewable and downloadable by members from the moment the
  delete completes — 0 successful member requests for any of its files afterwards.
- **SC-002**: A photo deleted on the server disappears from every member's device at their next
  sync, without clearing the app.
- **SC-003**: 100% of what one delete action sent to the trash comes back with one restore, and
  0 items that were in the trash before it come back with it.
- **SC-004**: 0 trashed items remain on the server — rows or files — more than one day after their
  purge date, given a daily purge.
- **SC-005**: 0 deletions go unrecorded: every item removed from the gallery, through the app or
  the Django admin, is in the trash and reported by the feed.
- **SC-006**: After the first sync, a sync made more than 90 s after the last change transfers no
  album or photo resource, and a sync after one change transfers only the items that change
  touched (plus, at most, items changed in the 90 s before the previous cursor).
- **SC-007**: An app version released before this feature keeps loading the gallery with no change
  to what it reads.
- **SC-008**: Each regression listed in FR-044 is covered by an automated check.

## Assumptions

- **Status codes.** Delete answers `204` (like 013's `DELETE …/cover/`); restore answers `200`
  with the restored resource, so the app can show it without another read.
- **"Who deleted" and "who uploaded" are display names**, shown only to owners in the trash. When
  the user was removed, the field is `null` and the item stays in the trash.
- **The trash listing is not paginated**, like every gallery list: a church gallery's trash
  holds tens of entries, and it is read by the management panel only.
- **Full sync size.** A feed read without `since` returns the whole gallery in one answer, as
  `GET /api/photos/` does today. Pagination is left for when the gallery outgrows it.
- **`full_sync_required: true` carries no items.** The request says the app then reconciles
  against the two list endpoints; the answer's cursor is issued before the app reads them, so any
  change made in between shows up again in the next delta, which the app applies idempotently.
- **An unreadable cursor is treated as expired** (Edge Cases), not as `400`: in a mobile app a bad
  stored cursor must heal itself on the next sync.
- **Order in the feed** (clarified). With `position` on both resources (FR-039a), the app orders
  siblings by `position`, then `id`, exactly as the server does, from its local copy.
- **Orphan files** (clarified). A file under `gallery/` that no row references (left by deletions
  in the Django admin before this feature) keeps the behaviour of spec 009: readable by members.
  Only files whose row is trashed are hidden (FR-024). The risk of the old admin deletions exists
  today and is accepted.
- **Trashed album covers only.** A cover file that was replaced or removed in 013 is deleted from
  disk after its change commits, so only covers of trashed albums need the media rule.
- **`updated_at` of existing rows.** Existing rows need a starting value; if the generated
  migration cannot give a meaningful one (for instance the photo's `uploaded_at`), a data
  migration with its reason at the top backfills it.
- **Scheduling the purge** (cron, systemd timer or similar) is a deploy concern for the plan and
  the deploy repository, not a requirement here.
- **Portuguese messages.** Refusals that reach the management panel (restore conflicts) are in
  Portuguese; not-found stays in English, as in 013.
- **Restore conflicts are `400`**, like 013's duplicate sibling name: the request is valid in
  form, but the gallery's state forbids it until the owner acts.
- **Only the batch root can conflict.** Its descendants' sibling sets could not change while they
  were trashed (Edge Cases), so FR-021 and FR-022 are checked on the item being restored only.

## Out of Scope

- Tagging members in photos and `Profile.member` (feature 015).
- Any Android app change, including deleting local files and the sync logic that consumes the
  feed.
- Push notifications: the feed is pulled by the app.
- A "delete forever" action or emptying the trash by hand (FR-025).
- A command to find or remove orphan `gallery/` files; a list-only command may come later.
- Soft delete for any other domain.
- Undo of a purge; restoring after the trash retention.
- Changing the file paths or names of existing gallery files.
