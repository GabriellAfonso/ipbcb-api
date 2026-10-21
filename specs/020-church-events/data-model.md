# Data Model: Church Events

## Event (`features/events/models/event.py`, table `events_event`)

| Field | Type | Null | Rule |
|-------|------|------|------|
| `id` | BigAutoField | no | |
| `title` | CharField(120) | no | trimmed, not blank |
| `start_date` | DateField | no | |
| `end_date` | DateField | yes | ≥ `start_date` (DB check constraint + domain rule) |
| `start_time` | TimeField | yes | hour and minute; seconds always 0 |
| `location` | CharField(200) | yes | never stored blank — blank becomes NULL |
| `description` | TextField | yes | never stored blank — blank becomes NULL |
| `image_path` | CharField(255), unique | no | storage name `events/{uuid}.jpg` |
| `visibility` | CharField(10), choices `public`/`members` | no | default `public` |
| `created_by` | FK `AUTH_USER_MODEL`, `SET_NULL` | yes | set on create, never changed |
| `created_at` | DateTimeField(auto_now_add) | no | |
| `updated_at` | DateTimeField(auto_now) | no | |

- `Meta.ordering = ["-start_date", "-id"]`, `verbose_name = "Event"`, `__str__` → title.
- Index on `start_date`. `image_path` is unique, hence indexed (media lookup, R-05).
- Check constraint `end_date IS NULL OR end_date >= start_date`.
- Derived, never stored: **last day** = `COALESCE(end_date, start_date)`; **active** =
  last day ≥ today in `America/Sao_Paulo`, queried as
  `end_date >= today OR (end_date IS NULL AND start_date >= today)`.

No change history, no soft delete. Deleting a user keeps their events (`created_by` → NULL).

## Domain (`features/events/domain/`)

- `event_dates.py`: `EVENTS_TIME_ZONE`, `today_in_events_zone(now) -> date`,
  `last_day(start, end) -> date`, `ensure_dates_ordered(start, end)` (raises
  `EventDatesInvalidError`).
- `event_image_rules.py`: `MAX_EVENT_IMAGE_BYTES` (10 MB), `EVENT_IMAGE_EXTENSIONS`
  (`jpg`, `png`, `webp`), `MIN_WIDTH`/`MIN_HEIGHT` (640/360), `TARGET_RATIO` (16/9),
  `RATIO_TOLERANCE` (0.02), `MAX_WIDTH`/`MAX_HEIGHT` (1920/1080), `MAX_PIXELS` (50 MP),
  `JPEG_QUALITY` (85); `ensure_event_image_shape(width, height)` raising `EventImageInvalidError`.
- `EventVisibility(StrEnum)`: `PUBLIC = "public"`, `MEMBERS = "members"`.
- `EventStatusFilter(StrEnum)`: `ACTIVE`, `PAST`, `ALL`; `parse_status_filter(raw)` raising
  `EventStatusFilterError`.

## DTOs (`features/events/dtos.py`, Pydantic)

- `EventCreatorDTO`: `id: UUID`, `name: str`.
- `EventRecordDTO`: every column but `created_by`'s FK id → `created_by: EventCreatorDTO | None`;
  `image_path` (the view builds the absolute URL).
- `EventCreateDTO`: `title`, `start_date`, `end_date | None`, `start_time | None`,
  `location | None`, `description | None`, `visibility` (default public). Validators strip text
  and turn blank into `None`; blank title raises.
- `EventPatchDTO`: same fields, all optional; `model_fields_set` decides what changes.
- The image travels beside the DTO as the uploaded stream (`IO[bytes]`), never inside it.
- `EventPatchDTO.resulting_dates(start, end)` gives the dates after the patch, for the date rule.

The service returns `EventRecordDTO`; the public serializer drops audit fields.

## Exceptions (`core/domain/event_exceptions.py`, re-exported from `core.domain.exceptions`)

| Exception | Base | Status | `field_errors` |
|-----------|------|--------|----------------|
| `EventNotFoundError(event_id)` | `NotFoundError` | 404 | — |
| `EventImageInvalidError(reason)` | `ValidationError` | 400 | `image` |
| `EventImageMissingError()` | `ValidationError` | 400 | `image` |
| `EventDatesInvalidError(start, end)` | `ValidationError` | 400 | `end_date` |
| `EventStatusFilterError(value)` | `ValidationError` | 400 | `status` |

Messages in Portuguese (they reach the app screen), naming the received value and the expected
shape.

## Repositories (`features/events/repositories/`)

- `EventRepository` protocol + `EventRepositoryImpl` (ORM only here):
  `list_active(today, include_members) -> list[EventRecordDTO]`,
  `get_active(event_id, today, include_members) -> EventRecordDTO | None`,
  `list_all(status, today) -> list[EventRecordDTO]`, `get(event_id) -> EventRecordDTO | None`,
  `create(dto, image_path, creator_id) -> EventRecordDTO`,
  `update(event_id, changes, image_path | None) -> EventRecordDTO`,
  `delete(event_id) -> None` (the service reads the image path first and removes the file).
  `select_related("created_by__profile")` — no query per row.
- `EventImageStorage` protocol + `DefaultStorageEventImageStorage`: `save(content) -> str`,
  `delete(name)`, `url(name)`.
- `EventImageLookupImpl` (implements media's `EventImageLookup`):
  `is_public_event_image(path) -> bool | None`, one indexed query.

## Services (`features/events/services/`)

- `EventService` (public + management reads): `list_visible(include_members)`,
  `get_visible(event_id, include_members)`, `list_for_management(status_raw)`,
  `get_for_management(event_id)`, `image_url_path(image_path)` (so views never touch storage).
- `EventWriteService`: `create_event(dto, image, creator_id)`,
  `update_event(event_id, dto, image | None)`, `delete_event(event_id)`.
- `EventImagePreparer`: validates the upload (R-04) and returns the JPEG bytes. Depends on
  `ImageProcessor` (core).

## Permissions (data migration `core/0008_events_owner_for_leader_media.py`)

| Role | `events` before | after |
|------|-----------------|-------|
| Admin | owner (code) | owner (code) |
| Liderança | manage | owner |
| Mídia | manage | owner |
