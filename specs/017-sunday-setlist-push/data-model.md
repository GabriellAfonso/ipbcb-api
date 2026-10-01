# Data Model: Sunday Worship Setlist with Push Distribution

Two generated migrations: `songs/0008` (setlist tables) and `core/0007` (device tokens). No data
migration. Existing tables are untouched.

---

## songs.Setlist (new)

One per date. The date is always a Sunday (enforced by the service, not the database: SQLite and
PostgreSQL disagree on weekday functions, and the rule's error must name the weekday).

| Field | Type | Constraints |
|-------|------|-------------|
| `date` | DateField | unique (`setlist_date_unique`) |
| `saved_by` | FK → `settings.AUTH_USER_MODEL` | null, `SET_NULL`, `related_name="+"` |
| `saved_at` | DateTimeField | set by the service from the injected clock on every save |
| `last_reminder_slot` | DateTimeField | null; start of the last reminder window claimed (R-10) |

- `Meta.ordering = ["-date"]`, `verbose_name = "setlist"`.
- `__str__`: `"Setlist 2026-10-04"`.
- `last_reminder_slot` is never reset by a save (R-08).

## songs.SetlistItem (new)

| Field | Type | Constraints |
|-------|------|-------------|
| `setlist` | FK → `Setlist` | `CASCADE`, `related_name="items"` |
| `position` | PositiveSmallIntegerField | 1–10 (check `setlist_item_position_range`) |
| `song` | FK → `Song` | `PROTECT`, `related_name="setlist_items"` |
| `tone` | CharField | max 3 |

- Unique `(setlist, position)` (`setlist_item_position_unique`).
- `Meta.ordering = ["setlist", "position"]`, `verbose_name = "setlist item"`.
- `__str__`: `"2026-10-04 #1 Song title"`.
- `PROTECT` on song: a song in any setlist cannot be deleted (spec Key Entities), same as `Played`.

## core.DeviceToken (new)

| Field | Type | Constraints |
|-------|------|-------------|
| `token` | CharField | max 512, unique (`device_token_unique`) |
| `user` | FK → `settings.AUTH_USER_MODEL` | `CASCADE`, `related_name="device_tokens"` |
| `updated_at` | DateTimeField | `auto_now` — last register call |

- `Meta.ordering = ["-updated_at"]`, `verbose_name = "device token"`.
- `__str__`: `"device token of <user_id>"` — never the token.
- Not registered in the Django admin: a token is a credential to a device.

## Read-only dependencies

| Model | Used for |
|-------|----------|
| `accounts.Profile.member` → `members.Member.ministries` → `members.Ministry.name` | worship membership (R-03), by lookup string only |
| `auth.Group`, `auth.Permission` on `core.PanelScope` | users with `manage` on `songs` (R-04) |
| `songs.Played.date` | "plays registered" for reminders and pending (R-10, R-12) |

---

## DTOs (Pydantic, `StrictBaseModel`)

### core

| DTO | Fields | Notes |
|-----|--------|-------|
| `PushMessage` | `type: PushMessageType`, `date: date` | `PushMessageType` StrEnum: `setlist_saved`, `confirm_plays`. `as_data()` → `{"type": ..., "date": "YYYY-MM-DD"}` (FCM data values are strings) |
| `PushSendReport` | `sent: int`, `failed: int`, `invalid_tokens: list[str]`, `aborted: bool`, `disabled: bool` | returned by `PushSender` |
| `PushOutcome` | `recipients: int`, `devices: int`, `sent: int`, `failed: int`, `invalid_removed: int`, `aborted: bool`, `disabled: bool` | returned by `PushService.notify`, logged |
| `WorshipFlagsDTO` | `is_worship_member: bool`, `can_save_setlist: bool` | profile flags |

### songs

| DTO | Fields |
|-----|--------|
| `SetlistItemInput` | `song_id: int`, `position: int` (1–10), `tone: str` (1–3, stripped) |
| `SetlistItemDTO` | `position`, `song_id`, `title`, `artist`, `tone` |
| `SetlistDTO` | `date: date`, `items: list[SetlistItemDTO]` (by position), `saved_by_name: str \| None`, `saved_at: datetime` |
| `ReminderRunReport` | `outcome: Literal["outside_window", "no_setlist", "confirmed", "already_sent", "sent"]`, `setlist_date: date \| None`, `slot: datetime \| None`, `push: PushOutcome \| None` |

`saved_by_name` is the author's `Profile.name`, falling back to the username; `None` when the
author was deleted.

---

## State: reminder slot of one setlist

```
last_reminder_slot = null
   │ run in window W (Sunday ≥ 21:00, no plays)
   ▼
last_reminder_slot = W  ──run in same W──▶ already_sent (no change)
   │ run in later window W' > W, still no plays
   ▼
last_reminder_slot = W'
   ⋮
any run after plays exist ──▶ confirmed (no change)
```

---

## Domain exceptions (new, `core/domain/setlist_exceptions.py`, re-exported by `core/domain/exceptions.py`)

| Exception | Base (status) | Message carries |
|-----------|---------------|-----------------|
| `NotWorshipMemberError` | `PermissionDeniedError` (403) | Portuguese detail for the app: "Disponível apenas para o ministério de Louvor." + `user_id` in context |
| `SetlistDateNotSundayError` | `ValidationError` (400) | the date and its weekday, expected "a Sunday" |
| `DuplicateSetlistPositionError` | `ValidationError` (400) | the repeated positions, expected unique |
| `SetlistNotFoundError` | `NotFoundError` (404) | the date |

Body shape errors (not an object, empty `items`, bad `song_id`/`position`/`tone`, bad date in the
URL) use the existing `ValidationError` through `core.http.parsing`. Missing songs reuse
`SongsNotFoundError` (404, `missing_song_ids`).
