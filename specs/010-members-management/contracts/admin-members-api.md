# Contract: Leader Members API

Base: `/ipbcb/`. Every route: JWT `Authorization: Bearer <access>`, `IsAuthenticated` +
`IsAdminUser`. Errors use the canonical body `{"error_code", "detail"}` (plus `field_errors`
for serializer errors).

Common errors on every route:

| Case | Status | `error_code` |
|---|---|---|
| No / invalid token | 401 | `NOT_AUTHENTICATED` / `AUTHENTICATION_FAILED` |
| Authenticated, not `is_admin` (or no profile) | 403 | `PERMISSION_DENIED` |
| `{id}` matches no member | 404 | `NOT_FOUND` |

Every `GET` answers `Cache-Control: private, no-store`, `Vary: Authorization`, an `ETag`, and
`304` when `If-None-Match` matches.

Shared shapes:

```json
// NamedRef
{"id": 3, "name": "Comungante"}

// MemberRecord
{
  "id": 12,
  "name": "Ana Souza",
  "first_name": "Ana",
  "last_name": "Souza",
  "birth_date": "1990-04-02",
  "gender": "F",
  "status": {"id": 1, "name": "Comungante"},
  "role": null,
  "ministries": [{"id": 2, "name": "Louvor"}, {"id": 5, "name": "Recepção"}],
  "baptism_date": "2005-06-12",
  "is_active": true,
  "photo_url": "https://host/ipbcb/media/members/6f1c2d0e....jpg",
  "created_at": "2026-09-25T14:02:11Z"
}
```

`photo_url` is `null` when there is no photo. It is readable only by leaders
(`specs/009-protected-media-access/`).

---

## GET `api/admin/members/`

200:

```json
{"members": [
  {"id": 12, "name": "Ana Souza", "photo_url": null,
   "status": {"id": 1, "name": "Comungante"}, "is_active": true}
]}
```

All members, `is_active` true and false, ordered by name. No pagination, no query params.

## POST `api/admin/members/`

Body (JSON object; only `name` required):

```json
{"name": "Ana Souza", "first_name": "Ana", "last_name": "Souza",
 "birth_date": "1990-04-02", "gender": "F", "status_id": 1, "role_id": null,
 "ministry_ids": [2, 5], "baptism_date": "2005-06-12", "is_active": true}
```

201: `MemberRecord`. History: one row `{"field": "created", "old_value": null, "new_value": null}`.
400 `VALIDATION_ERROR`: see `data-model.md`, Validation rules. Unknown keys (`photo`, `id`,
`created_at`, …) are rejected.

## GET `api/admin/members/{id}/`

200: `MemberRecord`.

## PATCH `api/admin/members/{id}/`

Body: any subset of the POST fields. `null` clears `status_id`, `role_id`, dates, `gender`;
`ministry_ids` replaces the whole list; `name` may not be null or blank.

200: `MemberRecord` after the edit. History: one row per field whose value changed. An empty
body or an all-unchanged body returns 200 and writes nothing.

## DELETE `api/admin/members/{id}/`

204, empty body. Removes member, all history, and (after commit) the photo file.

## PUT `api/admin/members/{id}/photo/`

`multipart/form-data`, field `photo`.

200:

```json
{"photo_url": "https://host/ipbcb/media/members/9ab0....png"}
```

400 `VALIDATION_ERROR`: field missing; not a decodable JPEG/PNG/WEBP/GIF; over 10 MB. The
current photo is untouched on 400. History: `{"field": "photo", "old_value": null,
"new_value": "photo changed"}`.

## DELETE `api/admin/members/{id}/photo/`

204, empty body. History: `{"field": "photo", "old_value": null, "new_value": "photo removed"}`
— only when there was a photo.

## GET `api/admin/members/{id}/history/`

200, newest first:

```json
{"history": [
  {"id": 40, "editor": {"id": "5b0e…-uuid", "name": "Pr. João"},
   "field": "ministries", "old_value": "Louvor, Recepção", "new_value": "Louvor",
   "changed_at": "2026-09-25T14:05:00Z"},
  {"id": 39, "editor": null, "field": "created", "old_value": null, "new_value": null,
   "changed_at": "2026-09-25T14:02:11Z"}
]}
```

`editor` is `null` when the editing account was deleted.

## GET `api/admin/members/options/`

200:

```json
{"statuses": [{"id": 1, "name": "Comungante"}, {"id": 2, "name": "Não comungante"}],
 "roles": [{"id": 1, "name": "Diácono"}],
 "ministries": [{"id": 2, "name": "Louvor"}, {"id": 5, "name": "Recepção"}]}
```

Each list ordered by name. Not tied to a member, so no 404.
