# Events Domain Spec

Church events — conferences, camps, special services — shown in the app's home carousel (the
app takes the three nearest) and on a detail screen, and managed from the app's panel.
Introduced by `specs/020-church-events/` (design, research, contract agreed with the app).

---

## Data Model

### Event (`features/events/models/event.py`)

| Field | Rule |
|-------|------|
| `title` | required, trimmed, not blank, ≤ 120 |
| `start_date` | required |
| `end_date` | optional, ≥ `start_date` (also a DB check constraint); absent = one-day event |
| `start_time` | optional, `HH:MM`, São Paulo local time, display and ordering only |
| `location` | optional, ≤ 200; blank stored as NULL |
| `description` | optional, long text; blank stored as NULL |
| `image_path` | required, unique; `events/{uuid}.jpg` |
| `visibility` | `public` (default) or `members` |
| `created_by` | user, `SET_NULL`; set on create, never changed |
| `updated_by` | user, `SET_NULL`; null on create, set to the caller on every successful PATCH |
| `created_at`, `updated_at` | automatic |

No soft delete, no history. Past events are kept indefinitely; only a delete removes one.

### Derived, never stored

- **Last day**: `end_date`, else `start_date`.
- **Active**: last day ≥ today in `America/Sao_Paulo` (`EVENTS_TIME_ZONE`), "today" from the
  injected clock on each request. Otherwise **past**. No scheduled job.

---

## Endpoints

| Method | Route | Access |
|--------|-------|--------|
| GET | `api/events/` | public; token optional |
| GET | `api/events/{id}/` | public; token optional |
| GET | `api/admin/events/?status=active\|past\|all` | `view` on `events` |
| POST | `api/admin/events/` (multipart) | `manage` on `events` |
| GET | `api/admin/events/{id}/` | `view` on `events` |
| PATCH | `api/admin/events/{id}/` (multipart) | `manage` on `events` |
| DELETE | `api/admin/events/{id}/` | `owner` on `events` |

Admin, Liderança and Mídia all hold `owner` on `events` (`core/0008`). Shapes, fields and
status codes: `specs/020-church-events/contracts/events-api.md`.

Every read answers with `ETag` / `304` and `Cache-Control: private, no-store` +
`Vary: Authorization` (bodies depend on the caller).

### Public resource

`id`, `title`, `start_date`, `end_date`, `start_time` (`"HH:MM"`), `location`, `description`,
`image_url` (absolute), `visibility`. Absent optional values are `null`.

### Management resource

Public resource plus `created_by` and `updated_by` (each `{id, name}` or `null`), `created_at`,
`updated_at`. The list is `{"events": [...]}`.

---

## Business Rules

1. **Public list**: active events visible to the caller, by `start_date` ascending, then
   `start_time` ascending with no time first, then id. No limit, no pagination.
2. **Visibility**: no token or a non-member (including a user with no profile row) sees only
   `public` events; a caller with member access (`Profile.member_access`, or an Admin/Liderança role — `specs/022-access-requests`) also sees `members` events. Roles grant
   nothing on the public endpoints.
3. **Hidden is missing**: a past event, or a `members` event for a non-member, answers `404` on
   the public detail and on its image, with the same body as an id that never existed.
4. **Invalid token** on a public endpoint is `401` (DRF authenticates first); the app refreshes.
5. **Management list**: every event, filtered by `status` (default `all`), by `start_date`
   descending, then `start_time` descending with no time last, then id descending. Unknown
   `status` is `400`. Management reads ignore visibility and the active window.
6. **Create**: multipart fields plus a required `image`. Blank `location`/`description` (and
   `""` on `end_date`/`start_time`) become `null`.
7. **Edit**: `PATCH` with any subset; `""` clears `end_date`, `start_time`, `location`,
   `description`; `title` and `start_date` cannot be cleared. The date rule is checked on the
   resulting event. Only the sent fields change.
8. **Image**: validated by decoded content — JPEG/PNG/WEBP, ≤ 10 MB, ≤ 50 MP, ≥ 640×360, ratio
   16:9 within ±2% measured after EXIF orientation — then stored as a JPEG (quality 85) fitted
   within 1920×1080, never upscaled, alpha flattened on white. The original is not kept.
   Limits are constants in `features/events/domain/event_image_rules.py`.
9. **Files follow the row**: a create or edit that fails after the new file was written removes
   it; a replaced image's old file is removed after the edit is saved; a delete removes the
   file after the row. A replaced image always gets a new name, so a URL never changes content.
10. **Image access** (media domain, `events/` folder): public event's image — anyone, no token
    needed; members event's image — members only; anything else `404`.

---

## Errors

| Scenario | Status | Code / field |
|----------|--------|--------------|
| Field invalid (blank title, missing/invalid date, bad time, unknown visibility) | 400 | `VALIDATION_ERROR`, `field_errors.<field>` |
| `end_date` before `start_date` | 400 | `field_errors.end_date` (`EventDatesInvalidError`) |
| Image missing | 400 | `field_errors.image` (`EventImageMissingError`) |
| Image invalid (format, size, pixels, dimensions, ratio, undecodable) | 400 | `field_errors.image` (`EventImageInvalidError`) |
| Unknown `status` filter | 400 | `field_errors.status` (`EventStatusFilterError`) |
| Missing, past (public) or hidden event | 404 | `NOT_FOUND` (`EventNotFoundError`) |
| No/invalid token on management | 401 | DRF |
| Missing level on `events` | 403 | `PERMISSION_DENIED` |

Messages are Portuguese and name the received value and the expected shape.

---

## Architecture

```
PublicEventListAPIView / PublicEventDetailAPIView      AllowAny + HasMemberAccess flag
AdminEventListAPIView / AdminEventDetailAPIView        IsAuthenticated + scope_permission(EVENTS)
  -> EventService            reads; "today" from Clock in São Paulo
  -> EventWriteService       create / update / delete; file cleanup
      -> EventImagePreparer  -> ImageProcessor (core/files/imaging, shared with the gallery)
  -> EventRepository (Protocol)    <- EventRepositoryImpl (ORM)
  -> EventImageStorage (Protocol)  <- DefaultStorageEventImageStorage
EventImageLookupImpl  implements media's EventImageLookup port
```

Everything wired in `config/di.py`. Domain exceptions in `core/domain/event_exceptions.py`.

---

## Future (not implemented)

- Push notification (FCM) when an event is published.
- "Add to calendar" button in the app.
- Registration link per event.
- "All events" screen in the app (the public list already returns every active event).
- "Past events" screen for members (past events are kept for it; today only management reads
  them).
- Draft events, scheduled publication, recurring events, trash/restore.
