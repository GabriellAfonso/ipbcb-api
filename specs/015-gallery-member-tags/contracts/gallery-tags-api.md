# Contract: Member Tags in Gallery Photos

Additions to `specs/013-gallery-write-api/contracts/gallery-api.md` and
`specs/014-gallery-trash-sync/contracts/gallery-trash-api.md`. Base path `/ipbcb/`, JWT in
`Authorization: Bearer`. Every error is the canonical `{"error_code", "detail"}` (spec 001),
sometimes with extra fields as listed. `401` for a missing or invalid token applies to every
route and is not repeated.

---

## Changes to existing resources

### Photo resource

Gains `members` as its last field, on every endpoint that returns it (lists, album list, upload,
`PATCH`, restore, change feed, and the tag writes below). Ordered by name, then id; `[]` when
untagged. Nothing else changes.

```json
{
  "id": 301, "name": "IMG_0042.jpg", "description": "", "album_id": 7,
  "album_name": "Retiro 2026", "image_url": "http://host/ipbcb/media/gallery/7/9b1e….jpg",
  "thumbnail_url": "http://host/ipbcb/media/gallery/thumbs/7/c4d0….jpg",
  "date_taken": "2026-03-14", "uploaded_at": "2026-03-15T10:00:00Z", "position": 0,
  "members": [ { "id": 40, "name": "João Lima" }, { "id": 12, "name": "Maria Souza" } ]
}
```

### Profile resource (`GET`/`PATCH /accounts/api/me/profile/`)

Gains `member_id` (integer or `null`), read-only. A `member_id` sent in `PATCH` is ignored, like
`is_member`.

```json
{ "name": "Maria Souza", "is_member": true, "photo_url": null,
  "roles": [], "permissions": { "gallery": null, "...": null }, "member_id": 12 }
```

---

## GET /api/photos/?member_id=…  ·  GET /api/albums/{id}/photos/?member_id=…

Permission: member (`IsMemberUser`), unchanged.

`member_id` may be repeated. With one or more values: only live photos tagged with **every**
listed member, in the endpoint's usual order (album endpoint: still only photos directly in the
album). Repeated values count once.

| Case | Status | Body |
|------|--------|------|
| filtered | `200` | array of Photo resources |
| a value matches no member | `200` | `[]` |
| a value is not an integer (`abc`, `1.5`, empty) | `400` | `VALIDATION_ERROR`, detail names the value |
| unknown or trashed album (album route) | `404` | `NOT_FOUND`, `album_id` (unchanged) |

---

## PUT /api/photos/{id}/members/

Permission: `manage` on `gallery` (method default). Body (JSON):

```json
{ "member_ids": [12, 40] }
```

Replaces the photo's tags with exactly this set. Repeated ids count once. `[]` clears.

| Case | Status | Body |
|------|--------|------|
| replaced (changed or not) | `200` | Photo resource |
| photo unknown or trashed | `404` | `NOT_FOUND`, `photo_id` |
| a member id unknown | `404` | `NOT_FOUND`, `missing_photo_ids: []`, `missing_member_ids: [...]` |
| body not an object, `member_ids` missing or not a list of integers | `400` | `VALIDATION_ERROR` |
| no `manage` on `gallery` | `403` | `PERMISSION_DENIED` (checked before existence) |

---

## POST /api/photos/members/

Permission: `manage` on `gallery` (method default). Body (JSON):

```json
{ "photo_ids": [301, 302], "add_member_ids": [12], "remove_member_ids": [40] }
```

Adds every (photo, added member) pair not yet tagged and removes every (photo, removed member)
pair that is; every other tag stays. Both member lists are optional and default to `[]`.
Repeated ids count once. Atomic: any refusal changes nothing.

| Case | Status | Body |
|------|--------|------|
| applied | `200` | array of Photo resources, in the order of first appearance in `photo_ids` |
| `photo_ids` empty, or both member lists empty | `400` | `VALIDATION_ERROR`, detail names the field |
| more than 200 distinct photos | `400` | `VALIDATION_ERROR`, `photo_count`, `limit` |
| an id in both member lists | `400` | `VALIDATION_ERROR`, `member_ids` |
| any photo unknown or trashed, any member unknown | `404` | `NOT_FOUND`, `missing_photo_ids`, `missing_member_ids` (every offending id, sorted) |
| body not an object, a list not of integers | `400` | `VALIDATION_ERROR` |
| no `manage` on `gallery` | `403` | `PERMISSION_DENIED` |

The `400` checks run before any database read, in the order listed.

---

## GET /api/gallery/taggable-members/

Permission: `manage` on `gallery` (**override** above the `GET` default `view`). Headers:
`Cache-Control: private, no-store`, `Vary: Authorization`, `ETag` (`304` on `If-None-Match`).

`200`: every member record, active or not, ordered by name, then id. Each entry has exactly these
two keys.

```json
[ { "id": 40, "name": "João Lima" }, { "id": 12, "name": "Maria Souza" } ]
```

| Case | Status |
|------|--------|
| no `manage` on `gallery` (a member without a role included) | `403` `PERMISSION_DENIED` |

---

## GET /api/gallery/tagged-members/

Permission: member (`IsMemberUser`). Same cache headers as the picker.

`200`: every member tagged in at least one live photo, ordered by name, then id.

```json
[ { "id": 40, "name": "João Lima", "photo_count": 3 },
  { "id": 12, "name": "Maria Souza", "photo_count": 17 } ]
```

`photo_count` counts live photos only. `403` for a caller who is not a member.

---

## Change feed (`GET /api/gallery/changes/`)

Shape unchanged (014); the Photo resources in `photos` carry `members`. A photo is returned in a
delta when its tags changed, or when a member tagged in it was renamed or deleted — through the
API or the Django admin. A tag write that changed nothing on a photo does not return it.

---

## Log line

```json
{ "event": "gallery_tags_changed", "photo_ids": [301, 302],
  "added": { "301": [12], "302": [12] }, "removed": { "301": [40] },
  "actor_id": "6f1c…" }
```

Emitted once per write that changed at least one tag. Ids only, never names.
