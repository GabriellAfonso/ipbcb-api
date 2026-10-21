# Contract: Events API

Base path `/ipbcb/` (nginx). All bodies JSON except the multipart writes. Errors use the canonical
shape `{"error_code", "detail", "field_errors"?}`.

## Public

### `GET api/events/`

- Auth: none required. `Authorization: Bearer <valid>` → members also get `members` events.
  Invalid/expired token → `401 AUTHENTICATION_FAILED`.
- `200`: `[EventPublic, ...]` — active events, `start_date` asc, `start_time` asc (null first),
  `id` asc. `[]` when none.
- Headers: `ETag`, `Cache-Control: private, no-store`, `Vary: Authorization`; `If-None-Match`
  match → `304`.

### `GET api/events/{id}/`

- Auth: as above.
- `200`: `EventPublic`. `404 NOT_FOUND` when the id does not exist, the event is past, or it is a
  `members` event and the caller is not a member — identical bodies.

### `EventPublic`

```json
{
  "id": 12,
  "title": "Congresso de Jovens",
  "start_date": "2026-11-14",
  "end_date": "2026-11-16",
  "start_time": "19:30",
  "location": "Templo principal",
  "description": "Três noites…",
  "image_url": "https://host/ipbcb/media/events/8c41….jpg",
  "visibility": "public"
}
```

`end_date`, `start_time`, `location`, `description` are `null` when absent.

## Management (JWT + level on scope `events`)

Missing/invalid token → `401`; no level → `403 PERMISSION_DENIED`. Responses `private, no-store`.

### `GET api/admin/events/?status=active|past|all` — `view`

- `200`: `{"events": [EventRecord, ...]}`, `start_date` desc, `start_time` desc (null last),
  `id` desc. Default `status=all`.
- `400 VALIDATION_ERROR`, `field_errors.status`, on an unknown value.

### `POST api/admin/events/` — `manage`, `multipart/form-data`

| Field | Required | Format |
|-------|----------|--------|
| `title` | yes | text, ≤ 120, not blank |
| `start_date` | yes | `YYYY-MM-DD` |
| `end_date` | no | `YYYY-MM-DD`, ≥ `start_date`; `""` = none |
| `start_time` | no | `HH:MM`; `""` = none |
| `location` | no | text ≤ 200; blank = none |
| `description` | no | text; blank = none |
| `visibility` | no | `public` (default) / `members` |
| `image` | yes | file: JPEG/PNG/WEBP, ≤ 10 MB, ≥ 640×360, 16:9 ± 2% |

- `201`: `EventRecord`.
- `400 VALIDATION_ERROR` with `field_errors` keyed by field (`title`, `start_date`, `end_date`,
  `start_time`, `visibility`, `image`).

### `GET api/admin/events/{id}/` — `view`

- `200`: `EventRecord` (past and `members` events included). `404` when missing.

### `PATCH api/admin/events/{id}/` — `manage`, `multipart/form-data`

- Any subset of the POST fields; `image` optional. Sending `end_date=""`, `start_time=""`,
  `location=""` or `description=""` clears it. `title` and `start_date` cannot be cleared.
- Date rule checked on the resulting event.
- `200`: `EventRecord`, `updated_by` set to the caller. A new image yields a new `image_url`;
  the old URL then answers `404`.
- `400` as POST; `404` when missing.

### `DELETE api/admin/events/{id}/` — `owner`

- `204`. Event and image file removed permanently. `404` when missing.

### `EventRecord`

`EventPublic` plus:

```json
{
  "created_by": { "id": "5b0e…-uuid", "name": "Ana Paula" },
  "updated_by": { "id": "a71d…-uuid", "name": "Beatriz" },
  "created_at": "2026-10-21T13:02:11Z",
  "updated_at": "2026-10-22T09:40:00Z"
}
```

`created_by` is `null` when the account is gone; `name` is the profile name (may be `""`).
`updated_by` has the same shape: the user of the last successful `PATCH` — any `200`, even one
that sent no field — `null` until the first edit and when that account is gone. A refused `PATCH`
leaves it unchanged. `EventPublic` never carries either.

## Media: `GET /ipbcb/media/events/{file}.jpg`

| Caller | Image of a `public` event | Image of a `members` event | No event for the file |
|--------|---------------------------|----------------------------|-----------------------|
| no token | `200` | `404` | `404` |
| invalid token | `401` | `401` | `401` |
| logged-in non-member | `200` | `404` | `404` |
| member | `200` | `200` | `404` |

`200` = the usual internal redirect with `Cache-Control: private, no-cache`; validators and `304`
from nginx. Path rules of spec 009 unchanged.

## Profile

`GET api/me/profile/` → `permissions.events` already present; now `owner` for Admin, Liderança
and Mídia, `null` for users without a role.
