---
description: "Task list for feature 017 — Sunday worship setlist with push distribution"
---

# Tasks: Sunday Worship Setlist with Push Distribution

**Input**: Design documents from `specs/017-sunday-setlist-push/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md),
[data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md)

**Tests**: included — CLAUDE.md §10 requires a test for every new function. Fakes are named
classes in `server/core/tests/fakes.py` and `server/features/songs/tests/fakes.py`; reuse
`FrozenClock` from the songs fakes.

**Decisions**: plan OQ-1 and OQ-2 answered A on 2026-10-01 — `Member.is_active` is not filtered;
credentials are base64 JSON in `FCM_SERVICE_ACCOUNT_JSON_BASE64`.

**Commits**: every commit must leave the whole tree passing mypy (memory: commit splitting). The
checkpoint at the end of each phase is a valid commit boundary. Spec and code go in the same
commit (CLAUDE.md §6.2).

All paths are relative to the repository root. Run commands from `server/` with `.venv_windows`.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on an unfinished task)
- **[Story]**: user story from spec.md (US1–US6)

---

## Phase 1: Setup (domain specs and configuration)

**Purpose**: spec-first updates and the one new setting. Commit with Phase 2's first code.

- [X] T001 [P] Update `specs/songs/spec.md`: add `Setlist` and `SetlistItem` to Data Models (fields, constraints, `PROTECT` on song, `last_reminder_slot` survives a re-save), the four endpoints from `specs/017-sunday-setlist-push/contracts/setlist-api.md`, the `send_setlist_reminders` command and its window rules, and Design Decisions entries (setlist vs `Played` separation; worship membership by ministry name "Louvor"; push after commit never fails the save)
- [X] T002 [P] Update `specs/accounts/spec.md`: `api/me/devices/` and `api/me/devices/unregister/` (from `contracts/me-api.md`), the `core.DeviceToken` entity as used by accounts, and `is_worship_member` / `can_save_setlist` on `GET/PATCH api/me/profile/`
- [X] T003 [P] Update `specs/members/spec.md`: note that the ministry named "Louvor" is load-bearing — renaming or deleting it in the Django admin disables setlist saving, distribution and reminders (logged as `worship_ministry_missing`)
- [X] T004 Add `FCM_SERVICE_ACCOUNT_JSON_BASE64 = os.environ.get("FCM_SERVICE_ACCOUNT_JSON_BASE64", "")` with a comment (empty = pushes disabled; never log the value) to `server/config/settings/base.py`, and the empty variable with a how-to comment (`base64 -w0 key.json`) to `.env.example`

---

## Phase 2: Foundational (shared `core` pieces)

**Purpose**: recipients queries, worship membership, device tokens and the push pipeline. Every
user story except US3 needs at least one of them.

**⚠️ CRITICAL**: no user story work starts before this phase is complete.

### Access: who holds a level on a scope (R-04)

- [X] T005 [P] Unit tests for `codenames_at_least` in `server/core/tests/unit/test_access.py` (`SONGS, MANAGE` → `{songs__manage, songs__owner}`; `VIEW` → all three; `OWNER` → one)
- [X] T006 [P] Integration tests for `user_ids_with_level` in `server/core/tests/integration/test_access_repository.py`: Admin (no stored permission) included; Leader included through `songs__manage`; Media excluded; user in an unrelated group holding the codename excluded; inactive user excluded; superuser without role excluded
- [X] T007 Add `codenames_at_least(scope: Scope, level: Level) -> frozenset[str]` with docstring example to `server/core/domain/access.py`
- [X] T008 Add `user_ids_with_level(scope, level) -> set[UUID]` to `RoleGrantRepository` protocol in `server/core/repositories/interfaces.py`, implement it in `server/core/repositories/access_repository.py` (Admin group ∪ role groups holding a codename from T007, `is_active=True`, two queries), add the passthrough to `AccessService` in `server/core/application/access_service.py`, and extend `FakeRoleGrantRepository` in `server/core/tests/fakes.py`

### Worship membership (R-03)

- [X] T009 [P] Create `server/core/domain/worship.py`: `WORSHIP_MINISTRY_NAME = "Louvor"` and `worship_name_pattern() -> str` (`^\s*<re.escape(lower name)>\s*$`); unit test in `server/core/tests/unit/test_worship.py` (matches `"Louvor"`, `" louvor "`, `"LOUVOR"`; rejects `"Louvor e Artes"`)
- [X] T010 [P] Integration tests in `server/core/tests/integration/test_worship_repository.py`: case/whitespace variants count; two matching ministries both count; profile without member → not a member; member outside the ministry → not; inactive user → not; `worship_ministry_exists` true/false; a member with `is_active=False` in "Louvor" still counts (OQ-1: A)
- [X] T011 Create `WorshipMembershipRepository` protocol in `server/core/repositories/interfaces.py` and `WorshipMembershipRepositoryImpl` in `server/core/repositories/worship_repository.py`: `is_worship_member(user_id) -> bool`, `worship_member_user_ids() -> set[UUID]`, `worship_ministry_exists() -> bool`, using `get_user_model()` and `profile__member__ministries__name__iregex` (lookup strings only — no import from `features`), `.distinct()`; no `Member.is_active` filter (OQ-1: A)
- [X] T012 [P] Add `FakeWorshipMembership` (configurable member ids, ministry-exists flag) to `server/core/tests/fakes.py`
- [X] T013 Create `server/core/application/dtos/worship_dtos.py` with `WorshipFlagsDTO(is_worship_member, can_save_setlist)`, and `server/core/application/worship_access_service.py` with `WorshipAccessService(membership_repository, access_service)`: `flags_for(user_id, grants) -> WorshipFlagsDTO`, `ensure_worship_member(user_id)` (raises `NotWorshipMemberError`), `setlist_recipients() -> set[UUID]`, `reminder_recipients() -> set[UUID]` (`user_ids_with_level(SONGS, MANAGE)` ∩ worship members); log `worship_ministry_missing` (warning, `ministry_name`) when recipients are computed and the ministry does not exist
- [X] T014 [P] Unit tests in `server/core/tests/unit/test_worship_access_service.py` for every method of T013 with `FakeWorshipMembership` and `FakeRoleGrantRepository`, including the empty-ministry warning
- [X] T015 Create `server/core/domain/setlist_exceptions.py` with `NotWorshipMemberError(PermissionDeniedError)` ("Disponível apenas para o ministério de Louvor.", `user_id` in context), `SetlistDateNotSundayError(ValidationError)` (date + weekday name, expected a Sunday), `DuplicateSetlistPositionError(ValidationError)` (repeated positions, expected unique), `SetlistNotFoundError(NotFoundError)` (date); re-export all four from `server/core/domain/exceptions.py`; unit tests in `server/core/tests/unit/test_setlist_exceptions.py` (status family, message carries the value, `extra_context`)
- [X] T016 Add `IsWorshipMember` permission class to `server/core/http/permissions.py` (authenticated and `is_worship_member`, resolved through a module-level `@inject` function like `_grants_for`; Portuguese message as in T015); unit test in `server/core/tests/unit/test_worship_permission.py`

### Device tokens and push pipeline (R-05, R-06, R-07, R-14, R-15)

- [X] T017 Create `DeviceToken` in `server/core/models/device_token.py` per `data-model.md` (token max 512 unique `device_token_unique`, user FK `CASCADE` `related_name="device_tokens"`, `updated_at` `auto_now`, `Meta.ordering`, `verbose_name`, `__str__` without the token); export from `server/core/models/__init__.py`; generate `server/core/migrations/0007_devicetoken.py` with `python manage.py makemigrations core`
- [X] T018 Create `DeviceTokenRepository` protocol in `server/core/repositories/interfaces.py` and `DeviceTokenRepositoryImpl` in `server/core/repositories/device_token_repository.py`: `register(user_id, token)` (`update_or_create`, moves ownership), `unregister(user_id, token) -> None`, `tokens_for(user_ids) -> list[str]` (one query), `delete_tokens(tokens) -> int`; integration tests in `server/core/tests/integration/test_device_token_repository.py`
- [X] T019 [P] Add `FakeDeviceTokenRepository` and `FakePushSender` (records calls, scripted per-token outcomes, can raise or abort) to `server/core/tests/fakes.py`
- [X] T020 [P] Create `server/core/domain/push.py`: `PushMessageType` StrEnum (`setlist_saved`, `confirm_plays`), `PushMessage(type, date)` with `as_data() -> dict[str, str]`; and `server/core/application/dtos/push_dtos.py`: `PushSendReport`, `PushOutcome` per `data-model.md`; unit test in `server/core/tests/unit/test_push_message.py`
- [X] T021 Create the port `PushSender` (Protocol, `send(tokens, message) -> PushSendReport`) in `server/core/push/sender.py` and `DisabledPushSender` in `server/core/push/disabled_sender.py` (sends nothing, `disabled=True`); add `server/core/push/__init__.py`
- [X] T022 Create `FcmPushSender` in `server/core/push/fcm_sender.py` per research R-05: `AuthorizedSession` from service-account info with the `firebase.messaging` scope, URL `https://fcm.googleapis.com/v1/projects/{project_id}/messages:send`, body with `data` and `android.priority = "HIGH"`, timeouts `(3.05, 5)`; 200 → sent; 404 or `errorCode` `UNREGISTERED`/`NOT_FOUND` in `error.details` → invalid; other status → failed; `requests.RequestException` or `google.auth.exceptions.RefreshError` → abort the batch, remaining tokens counted failed. Session injected through the constructor so tests pass a fake. Keep functions ≤ 20 lines (split response classification into its own function)
- [X] T023 [P] Unit tests in `server/core/tests/unit/test_fcm_push_sender.py` with a named `FakeHttpSession`: 200; 404 `UNREGISTERED`; 400 `INVALID_ARGUMENT` kept (not invalid); 500 failed; timeout on 2nd of 4 tokens aborts with 1 sent, 3 failed; request body shape (data strings, HIGH priority, token)
- [X] T024 Create `build_push_sender(encoded_credentials: str) -> PushSender` in `server/core/push/factory.py`: empty → `DisabledPushSender`; otherwise base64-decode, parse JSON, require `project_id`, `client_email`, `private_key` (raise `ImproperlyConfigured` naming the missing key or the decode failure, never echoing the value) → `FcmPushSender`; unit tests in `server/core/tests/unit/test_push_factory.py`
- [X] T025 Add `PUSH_MESSAGES_COUNTER` (`ipbcb_push_messages_total`, labels `type`, `outcome`) to `server/core/metrics.py`
- [X] T026 Create `PushService(token_repository, sender)` in `server/core/application/push_service.py`: `notify(user_ids, message) -> PushOutcome` — no recipients or no tokens → outcome without calling the sender; send; delete `invalid_tokens`; log `push_sent` / `push_disabled` / `push_transport_error` per R-15 (ids and counts only, never tokens); increment T025; catch every exception from the sender, log it with `error_class`, return an outcome — never raise
- [X] T027 [P] Unit tests in `server/core/tests/unit/test_push_service.py`: empty recipients; recipients without devices; invalid tokens deleted; abort logged; disabled logged as warning; sender raising → no exception, outcome `failed`; log records contain no token string
- [X] T028 Register in `server/config/di.py`: `worship_membership_repository`, `worship_access_service`, `device_token_repository`, `push_sender = providers.Singleton(build_push_sender, encoded_credentials=providers.Callable(lambda: settings.FCM_SERVICE_ACCOUNT_JSON_BASE64))` (read at provision, so `override_settings` reaches it), `push_service`; wire `core.http.permissions` (already wired)

**Checkpoint**: `pytest core -q` and `mypy .` green — commit together with T001–T004.

---

## Phase 3: User Story 1 — Worship leader saves the Sunday setlist (Priority: P1) 🎯 MVP

**Goal**: `PUT api/setlists/{date}/` stores or fully replaces one Sunday's setlist, refusing
non-members, non-Sundays, empty lists, repeated positions and unknown songs.

**Independent Test**: as a Liderança user in "Louvor", save, read back by date (direct repository
query in the test), save a different list for the same date, check only the second remains;
each refusal returns its status without writing.

### Tests for User Story 1

- [X] T029 [P] [US1] Unit tests in `server/features/songs/tests/unit/test_setlist_rules.py`: `ensure_sunday` (Sunday ok; Monday raises naming `2026-10-05` and the weekday), `ensure_unique_positions` (ok; `[1, 2, 2, 3, 3]` raises naming `[2, 3]`)
- [X] T030 [P] [US1] Unit tests in `server/features/songs/tests/unit/test_setlist_dtos.py`: `parse_setlist_date` (valid; `"2026-13-01"`, `"04/10/2026"`, `""` → `ValidationError`), `parse_setlist_items` (non-object body, missing/empty/non-list `items`, item not an object, non-integer `song_id`/`position`, position 0 and 11, `tone` missing/empty/4 chars/non-string, tone stripped)
- [X] T031 [P] [US1] Unit tests in `server/features/songs/tests/unit/test_setlist_service.py` for `save` with `FakeSetlistRepository`, `FakeWorshipMembership`, `FakePushSender`-backed `PushService`, `FrozenClock`: non-member raises `NotWorshipMemberError` before any write; non-Sunday; duplicate positions; missing songs → `SongsNotFoundError` listing ids, nothing written; success returns the DTO with `saved_at` from the clock
- [X] T032 [P] [US1] Integration tests in `server/features/songs/tests/integration/test_setlist_api.py` (save part): 401; Media user 403; Liderança not in "Louvor" 403 with the Portuguese detail; Admin in "Louvor" 200; 400 for each body error, non-Sunday and repeated positions; 404 with `missing_song_ids`; second save replaces all items and updates author/time; `Cache-Control: private, no-store`; a song in a setlist cannot be deleted (`ProtectedError`)

### Implementation for User Story 1

- [X] T033 [US1] Create `Setlist` and `SetlistItem` in `server/features/songs/models/setlist.py` per `data-model.md` (constraints `setlist_date_unique`, `setlist_item_position_unique`, `setlist_item_position_range`; `Meta.ordering`, `verbose_name`, `__str__`); export from `server/features/songs/models/__init__.py`; generate `server/features/songs/migrations/0008_setlist_setlistitem.py` with `python manage.py makemigrations songs`
- [X] T034 [P] [US1] Create `server/features/songs/setlist_dtos.py`: `SetlistItemInput`, `SetlistItemDTO`, `SetlistDTO` per `data-model.md`; `parse_setlist_date(raw: str) -> date` and `parse_setlist_items(payload: object) -> list[SetlistItemInput]` using `require_object_body` / `require_int` from `core.http.parsing`, messages naming the offending value and the expected shape
- [X] T035 [P] [US1] Create `server/features/songs/services/setlist_rules.py` with `ensure_sunday(day: date)` and `ensure_unique_positions(items)` (docstring examples)
- [X] T036 [US1] Add `SetlistRepository` protocol to `server/features/songs/repositories/interfaces.py` (`replace`, `get_by_date`; later phases add the rest) and implement `SetlistRepositoryImpl` in `server/features/songs/repositories/setlist_repository.py`: `replace(day, author_id, items, saved_at) -> SetlistDTO` inside `transaction.atomic()` with `get_or_create` + `select_for_update` + delete items + `bulk_create`, `last_reminder_slot` untouched (R-08); `get_by_date(day) -> SetlistDTO | None` with items and songs in one prefetch; `saved_by_name` = profile name or username via lookup strings; integration tests in `server/features/songs/tests/integration/test_setlist_repository.py` (create, replace, reminder slot preserved, ordering)
- [X] T037 [P] [US1] Add `FakeSetlistRepository` to `server/features/songs/tests/fakes.py`
- [X] T038 [US1] Create `SetlistService(setlist_repository, song_repository, worship_access_service, push_service, clock)` in `server/features/songs/services/setlist_service.py` with `save(author_id, day, items) -> SetlistDTO`: membership → `ensure_sunday` → `ensure_unique_positions` → songs exist via `song_repository.get_songs_in_bulk` (raise `SongsNotFoundError`) → `replace` → log `setlist_saved` (`setlist_date`, `user_id`, `item_count`, `replaced`). Push call added in US2
- [X] T039 [US1] Create `SetlistByDateAPI` in `server/features/songs/views/setlists.py` with `put` (`IsAuthenticated`, `scope_permission(Scope.SONGS, {"GET": Level.MANAGE})`; parse date and body, call `save`, answer 200 through `_not_modified_or_response(..., private=True)` or an equivalent private response); route `api/setlists/<str:day>/` in `server/features/songs/urls.py`
- [X] T040 [US1] Register `setlist_repository` and `setlist_service` in `server/config/di.py` and wire `features.songs.views.setlists`

**Checkpoint**: US1 tests green; commit.

---

## Phase 4: User Story 2 — Worship members receive the setlist by push (Priority: P1)

**Goal**: every save pushes `setlist_saved` to all worship members' devices; members read the
current setlist as fallback.

**Independent Test**: with `FakePushSender` overriding `push_sender`, save and check exactly the
worship members' tokens were addressed; read `current/` as member and non-member.

### Tests for User Story 2

- [X] T041 [P] [US2] Extend `server/features/songs/tests/unit/test_setlist_service.py`: save calls `PushService.notify` with `setlist_recipients()` and `PushMessage(setlist_saved, day)` after `replace`; a push outcome of failure still returns the setlist; re-save pushes again; `current(today)` returns earliest date ≥ today or `None`
- [X] T042 [P] [US2] Extend `server/features/songs/tests/integration/test_setlist_api.py`: three worship members with devices + one outsider → only members' tokens sent, author included; sender raising → 200 and setlist stored; `UNREGISTERED` token removed from the table; `GET api/setlists/current/` returns next Sunday on a weekday, `{"setlist": null}` when none, 403 for a non-member, private cache headers

### Implementation for User Story 2

- [X] T043 [US2] Add `current(today) -> SetlistDTO | None` to the protocol and `SetlistRepositoryImpl` (`date__gte=today`, earliest), and to `FakeSetlistRepository`
- [X] T044 [US2] In `SetlistService.save` call `push_service.notify(worship_access_service.setlist_recipients(), PushMessage(PushMessageType.SETLIST_SAVED, day))` after `replace` returns (outside the transaction); add `current() -> SetlistDTO | None` using `timezone.localdate(clock.now())`
- [X] T045 [US2] Add `CurrentSetlistAPI` (`IsAuthenticated`, `IsWorshipMember`; `{"setlist": ... | null}`, private) to `server/features/songs/views/setlists.py`; route `api/setlists/current/` **before** `api/setlists/<str:day>/` in `server/features/songs/urls.py`

**Checkpoint**: US1 + US2 green; commit.

---

## Phase 5: User Story 3 — Devices register and unregister for push (Priority: P1)

**Goal**: the app registers its FCM token on login/rotation and removes it on logout.

**Independent Test**: register, register the same token as another user, unregister as the
wrong user, unregister as the owner — check ownership and existence after each call.

### Tests for User Story 3

- [X] T046 [P] [US3] Unit tests in `server/core/tests/unit/test_device_token_service.py` with `FakeDeviceTokenRepository`: valid token stored; whitespace trimmed; empty, over 512 chars, inner whitespace, non-string → `ValidationError` naming the length/shape; unregister delegates
- [X] T047 [P] [US3] Integration tests in `server/features/accounts/tests/integration/test_device_api.py`: 401 without JWT on both; register 204; repeat 204 with one row; same token by user B moves it; unregister by A afterwards changes nothing and is 204; unregister by owner deletes; unknown token 204; malformed body 400

### Implementation for User Story 3

- [X] T048 [US3] Create `DeviceTokenService(token_repository)` in `server/core/application/device_token_service.py`: `register(user_id, raw_token)`, `unregister(user_id, raw_token)`, sharing one `_valid_token(raw) -> str` validator (R-14)
- [X] T049 [US3] Create `DeviceTokenRegisterAPI` and `DeviceTokenUnregisterAPI` (`IsAuthenticated`, `require_object_body`, 204) in `server/features/accounts/views/devices.py`; routes `api/me/devices/` and `api/me/devices/unregister/` in `server/features/accounts/urls.py`
- [X] T050 [US3] Register `device_token_service` in `server/config/di.py` and wire `features.accounts.views.devices`

**Checkpoint**: P1 stories complete — the MVP is deliverable to the app; commit.

---

## Phase 6: User Story 4 — The app knows what the user can do (Priority: P2)

**Goal**: `is_worship_member` and `can_save_setlist` on the profile.

**Independent Test**: read the profile for the four combinations of `manage` on `songs` × worship
membership and check both flags; change ministries and check the ETag changes.

- [X] T051 [P] [US4] Extend `server/features/accounts/tests/integration/test_profile_api.py`: four combinations; user with role but no linked member → both false; ETag differs after adding the member to "Louvor"; `PATCH` ignores both fields
- [X] T052 [P] [US4] Extend `server/features/accounts/tests/unit/test_profile_serializer.py`: missing `worship_flags` context raises `KeyError` naming the expected type (same guard as `access_grants`)
- [X] T053 [US4] In `server/features/accounts/views/profile.py`, inject `WorshipAccessService` into `get` and `patch` and add `"worship_flags": worship_access_service.flags_for(user.pk, grants)` to `_serializer_context`; in `server/features/accounts/serializers/serializers.py` add read-only `is_worship_member` and `can_save_setlist` to `ProfileSerializer` (fields and `read_only_fields`) backed by a `_worship_flags()` guard

**Checkpoint**: commit.

---

## Phase 7: User Story 5 — Sunday night reminder to confirm the played songs (Priority: P2)

**Goal**: from 21:00 on the setlist's Sunday, every 30 min until midnight, `confirm_plays` goes to
worship members with `manage` on `songs`, once per window, until plays are registered.

**Independent Test**: spec US5 scenario with `FrozenClock` and `FakePushSender`: runs at 20:59,
21:05, 21:10, 21:35, 22:01, then plays registered, run at 22:31 → sends at 21:05, 21:35, 22:01 only.

### Tests for User Story 5

- [X] T054 [P] [US5] Unit tests in `server/features/songs/tests/unit/test_reminder_slot.py` for `current_reminder_slot`: Sunday 20:59 → None; 21:00 → 21:00; 21:29 → 21:00; 21:30 → 21:30; 23:59 → 23:30; Saturday 22:00 → None; result keeps the local timezone
- [X] T055 [P] [US5] Unit tests in `server/features/songs/tests/unit/test_setlist_reminder_service.py`: the Independent Test sequence; `outside_window`; `no_setlist`; `confirmed`; `already_sent` after a simulated restart (new service instance, same repository); process down 21:00–22:40 → single send for 22:30; sender failure still claims the window; recipients are `reminder_recipients()`
- [X] T056 [P] [US5] Integration tests in `server/features/songs/tests/integration/test_setlist_reminder_repository.py`: `claim_reminder_slot` true on first claim, false on the same slot, true on a later slot, false on an earlier one; `has_plays(day)` true with any `Played` row for the date
- [X] T057 [P] [US5] Command test in `server/features/songs/tests/integration/test_send_setlist_reminders_command.py`: `call_command("send_setlist_reminders")` prints one summary line with `outcome=` and exits without error outside the window

### Implementation for User Story 5

- [X] T058 [US5] Add `current_reminder_slot(now_local: datetime) -> datetime | None` to `server/features/songs/services/setlist_rules.py` (constants `REMINDER_START = time(21, 0)`, `REMINDER_STEP_MINUTES = 30`)
- [X] T059 [US5] Add `has_plays(day) -> bool` and `claim_reminder_slot(setlist_date, slot) -> bool` (single conditional `UPDATE`, R-10) to the protocol, `SetlistRepositoryImpl` and `FakeSetlistRepository`; add `ReminderRunReport` to `server/features/songs/setlist_dtos.py`
- [X] T060 [US5] Create `SetlistReminderService(setlist_repository, worship_access_service, push_service, clock)` in `server/features/songs/services/setlist_reminder_service.py`: `run() -> ReminderRunReport` following R-10 steps 1–6, logging `setlist_reminder_run` (`outcome`, `setlist_date`, `slot`); split into ≤ 20-line functions
- [X] T061 [US5] Create `server/features/songs/management/__init__.py`, `server/features/songs/management/commands/__init__.py` and `server/features/songs/management/commands/send_setlist_reminders.py` (module-level `@inject` function like `purge_gallery_trash.py`, one `summary_line(report)` output, always exit 0); register `setlist_reminder_service` in `server/config/di.py` and wire the command module
- [X] T062 [US5] Add service `ipbcb_setlist_reminder` (container `ipbcb-setlist-reminder-prod`) to `compose.prod.yml`, cloned from `ipbcb_token_flush`: loop `python manage.py send_setlist_reminders; sleep 60`, same image, `./.env`, pinned `DJANGO_ENV`/`DJANGO_SETTINGS_MODULE`, same `depends_on`, `restart: unless-stopped`, comment explaining why (spec 017 FR-021, no task queue)

**Checkpoint**: commit.

---

## Phase 8: User Story 6 — Managers see Sundays pending confirmation (Priority: P3)

**Goal**: list setlists on or before today without registered plays; read any setlist by date.

**Independent Test**: setlists for three past Sundays and today, plays for one → list holds the
other three newest first; by-date returns one and 404 for a date without setlist.

- [X] T063 [P] [US6] Extend `server/features/songs/tests/integration/test_setlist_api.py`: pending order newest first; future excluded; disappears after plays registered; empty list; Media 403; Liderança not in "Louvor" 200 (membership not required); `GET api/setlists/{date}/` 200, 404 `NOT_FOUND`, 400 bad format, 403 for Media
- [X] T064 [P] [US6] Extend `server/features/songs/tests/unit/test_setlist_service.py`: `by_date` raises `SetlistNotFoundError`; `pending` uses local today from the clock
- [X] T065 [US6] Add `pending(today) -> list[SetlistDTO]` (`date__lte`, `~Exists(Played …)`, `-date`, one prefetch — R-12) to the protocol, `SetlistRepositoryImpl` and `FakeSetlistRepository`; add `by_date(day)` and `pending()` to `SetlistService`
- [X] T066 [US6] Add `get` to `SetlistByDateAPI` and create `PendingConfirmationSetlistsAPI` (`scope_permission(Scope.SONGS, {"GET": Level.MANAGE})`, private) in `server/features/songs/views/setlists.py`; route `api/setlists/pending-confirmation/` before `api/setlists/<str:day>/` in `server/features/songs/urls.py`

**Checkpoint**: commit.

---

## Phase 9: Polish & cross-cutting

- [x] T067 [P] Replace `FixedClock` with `FrozenClock` (the existing songs fake) in `specs/017-sunday-setlist-push/plan.md` and `specs/017-sunday-setlist-push/quickstart.md`
- [X] T068 [P] Check every new file is under 500 lines and every function 4–20 lines; split where not (`server/core/push/fcm_sender.py`, `server/features/songs/views/setlists.py`, `server/features/songs/services/setlist_service.py` are the likeliest)
- [X] T069 Run from `server/`: `python -m pytest -q`, `python -m mypy .`, `ruff check .`, `bandit -r core features -q`, `python manage.py makemigrations --check --dry-run`
- [ ] T070 Run `specs/017-sunday-setlist-push/quickstart.md` §2 and §3 locally; §4 (real FCM, SC-001/SC-002 timing) and §5 (migrations on a production dump with rollback) are deploy-time and stay listed in the PR description
- [X] T071 Mark the implemented parts done in `specs/017-sunday-setlist-push/tasks.md` and confirm `specs/songs/spec.md` / `specs/accounts/spec.md` describe what was built (CLAUDE.md §6.2)

---

## Dependencies & Execution Order

### Phases

- **Setup (T001–T004)** → no dependencies.
- **Foundational (T005–T028)** → after Setup; blocks every story except US3's endpoint layer,
  which only needs T017–T019.
- **US1 (T029–T040)** → after Foundational.
- **US2 (T041–T045)** → after US1 (extends `SetlistService` and the setlist views).
- **US3 (T046–T050)** → after T017–T019 only; independent of US1/US2.
- **US4 (T051–T053)** → after T009–T016; independent of setlists.
- **US5 (T054–T062)** → after US1 (models, repository) and Foundational push.
- **US6 (T063–T066)** → after US1.
- **Polish (T067–T071)** → last.

### Story graph

```
Setup ─▶ Foundational ─┬─▶ US1 ─┬─▶ US2
                       │        ├─▶ US5
                       │        └─▶ US6
                       ├─▶ US3   (needs only device-token pieces)
                       └─▶ US4   (needs only worship pieces)
```

### Within each story

Tests first and failing → models → repository → service → view/URL → DI.

## Parallel Opportunities

- Setup: T001, T002, T003 together.
- Foundational: T005/T006 (tests), T009, T010, T012, T019, T020 in parallel; T023, T027 alongside
  their implementations' neighbours.
- After Foundational: US1, US3 and US4 can proceed in parallel; after US1, US2, US5 and US6 can.

### Example: User Story 1

```text
Together: T029 test_setlist_rules.py | T030 test_setlist_dtos.py | T031 test_setlist_service.py | T032 test_setlist_api.py
Then:     T033 models + migration
Together: T034 setlist_dtos.py | T035 setlist_rules.py | T037 FakeSetlistRepository
Then:     T036 repository → T038 service → T039 view/URL → T040 DI
```

### Example: User Story 5

```text
Together: T054 | T055 | T056 | T057
Then:     T058 → T059 → T060 → T061 → T062
```

## Implementation Strategy

### MVP (P1: US1 + US2 + US3)

1. Setup + Foundational.
2. US1 → save works (testable alone, push not yet sent).
3. US3 → devices register (testable alone).
4. US2 → saves reach phones. **Stop and validate** with quickstart §2, then deploy with real
   credentials (quickstart §4) — this is the first release the band notices.

### Incremental

5. US4 → the app hides actions the user cannot take.
6. US5 → Sunday night reminders (needs the new container in production).
7. US6 → admin panel card.

Each phase ends at a commit that keeps the whole tree type-correct.
