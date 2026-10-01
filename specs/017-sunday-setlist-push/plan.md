# Implementation Plan: Sunday Worship Setlist with Push Distribution

**Branch**: `017-sunday-setlist-push` | **Date**: 2026-10-01 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/017-sunday-setlist-push/spec.md`

## Summary

`songs` gains `Setlist` (one per Sunday) and `SetlistItem`, saved with `PUT api/setlists/{date}/`
(full replacement under a row lock) and read as current, by date, and as "pending confirmation".
`core` gains `DeviceToken`, a project-owned push port with an FCM HTTP v1 adapter on google-auth +
requests, a `PushService` that deletes tokens FCM reports as unregistered, and the worship
membership query (ministry named "Louvor", by lookup string, no feature import). Saving sends
`setlist_saved` to every worship member's devices after commit; a failure is logged and never
fails the save. A compose loop runs `send_setlist_reminders` every 60 s: on the setlist's Sunday
from 21:00, it claims the current half-hour window on the setlist row with a conditional update
and sends `confirm_plays` to worship members holding `manage` on `songs`, until a `Played` row
exists for the date. The profile gains `is_worship_member` and `can_save_setlist`; `accounts`
gains `api/me/devices/` register/unregister.

## Technical Context

**Language/Version**: Python 3.14, `.venv_windows`

**Primary Dependencies**: Django 6.0, DRF 3.17, dependency-injector, Pydantic 2.12, google-auth
2.x and requests 2.33 (both already pinned; no new dependency).

**Storage**: PostgreSQL in production, SQLite in tests. Generated migrations `songs/0008`,
`core/0007`. No data migration.

**Testing**: pytest + pytest-django; named fakes (`FakePushSender`, `FakeDeviceTokenRepository`,
`FakeWorshipMembership`, `FakeSetlistRepository`, `FrozenClock`, a fake HTTP session for the FCM
adapter); mypy, ruff, bandit.

**Target Platform**: Linux containers behind nginx, prefix `/ipbcb/`; new container
`ipbcb_setlist_reminder`.

**Project Type**: Web service (REST API), single Android client.

**Performance Goals**: save including push < 3 s with the whole worship ministry registered,
provider up or down (SC-002); push received < 1 min (SC-001); reminder window sent within its
first ~2 min.

**Constraints**: no Celery or new dependency; credentials only from the environment; services
never see HTTP; ORM only in repositories; features never import each other; `Played` and
`POST api/played/register/` unchanged; files < 500 lines, functions 4–20 lines.

**Scale/Scope**: tens of worship members, tens of devices, one setlist a week; 4 + 2 endpoints,
3 models, 1 command, 1 container.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design; result unchanged.*

| Rule (`specs/constitution.md`, `CLAUDE.md`) | Status |
|---|---|
| `IsAuthenticated` on every view | ✅ all six endpoints |
| Management endpoints declare exactly one scope; levels only from roles via scopes | ✅ save, by-date, pending: `scope_permission(Scope.SONGS)` (`GET` overrides raise to `manage`). No role checked by name (clarification Q1) |
| Church membership never grants a level | ✅ worship membership only narrows (`can_save` = scope **and** membership); `current/` is not a management endpoint and is gated by membership alone, like `IsMemberUser` (R-02) |
| Features never import each other | ✅ shared pieces in `core` (R-01); members/accounts traversed by lookup strings |
| `core` models only if shared by ≥ 2 features | ✅ `DeviceToken`: written by `accounts`, read by `songs` |
| Views → services → repositories; ORM only in repositories | ✅ |
| Services never import HTTP | ✅ FCM HTTP lives in the `core/push` adapter behind `PushSender`, not in a service |
| Wrap third-party libs behind a project interface | ✅ `PushSender` port; google-auth/requests only in `FcmPushSender` |
| Input validated before the database; `require_object_body` / `require_int` | ✅ R-09 |
| No queries in loops | ✅ recipients = two set queries (R-03, R-04); pending = one query + prefetch (R-12) |
| Domain exceptions with offending value and expected shape | ✅ data-model, new `setlist_exceptions.py` |
| DI via `config/di.py`; Pydantic DTOs | ✅ |
| No hardcoded secrets; each service gets only its secrets | ✅ `FCM_SERVICE_ACCOUNT_JSON_BASE64` in `./.env`, read by server and reminder only (R-06) |
| Members data sensitive: ids only in logs | ✅ R-15; push payload carries type and date only |
| Caller-dependent responses private | ✅ every endpoint through `private=True` |
| Error shape canonical | ✅ contracts |
| Migrations generated | ✅ two `CreateModel` migrations; dump round trip anyway (quickstart §5) |
| Models: `__str__`, `Meta.ordering`, `verbose_name` | ✅ data-model |
| Spec before code, same commit | ✅ step 0 |

Gate: **pass**. No deviations.

## Technical Decisions

Full reasoning in [research.md](research.md).

- **D-1** Placement: setlist in `songs`; tokens, push, worship membership in `core`; device
  endpoints in `accounts` (R-01).
- **D-2** Authorization table: scope `songs` `manage` on save/by-date/pending; worship check in
  `SetlistService`; new `IsWorshipMember` on `current/` (R-02).
- **D-3** Worship membership by `iregex` on the ministry name through
  `profile__member__ministries`, active users only (R-03).
- **D-4** `codenames_at_least` + `user_ids_with_level` for "who holds `manage` on `songs`" (R-04).
- **D-5** `PushSender` port; `FcmPushSender` (AuthorizedSession, one request per token, HIGH
  priority, abort batch on transport error, only `UNREGISTERED`/`NOT_FOUND`/404 delete);
  `DisabledPushSender` when unconfigured; Singleton (R-05).
- **D-6** Credentials as base64 JSON in one env var (R-06) (OQ-2: A).
- **D-7** Push synchronous after commit; `PushService` never raises (R-07).
- **D-8** Replace under `select_for_update`; `last_reminder_slot` survives a re-save (R-08).
- **D-9** View parses shape; service checks membership, Sunday, positions, songs (R-09).
- **D-10** Reminder: pure slot function, claim-before-send conditional update, only the current
  window (R-10). Compose loop every 60 s (R-11).
- **D-11** `PUT` for save (idempotent full replacement keyed by date); `POST …/unregister/` for
  token removal so the token never enters a URL (R-14).

## Resolved questions

Both answered on 2026-10-01 with option A.

### OQ-1 — Does an inactive member record (`Member.is_active = False`) still count for "Louvor"?

`Member.is_active` means "valid profile" in the members spec; invalid records are hidden from the
member list and birthdays. Nothing in the setlist spec mentions it.

| Option | Effect |
|--------|--------|
| **A** — ignore it (**chosen**) | A user linked to an invalid record still gets setlists if the record lists "Louvor". Simplest; the link is set by hand in the admin, so a wrong link is the admin's to fix. |
| B — require `is_active = True` | Matches how the rest of the app treats invalid records; one more filter in R-03. A member marked invalid by mistake silently stops receiving setlists. |

### OQ-2 — Credential format

| Option | Effect |
|--------|--------|
| **A** — `FCM_SERVICE_ACCOUNT_JSON_BASE64`: whole JSON, base64, one line in `.env` (**chosen**) | One secret location, no volume; you run `base64 -w0 key.json` once |
| B — `FCM_CREDENTIALS_FILE`: path to a JSON file mounted into both containers | Key stays a file; adds a volume to two compose services, a host file outside the repo, and its permissions |

## Spec adjustments made while planning

None to the feature spec. Domain specs updated in step 0 (below).

## Adjustments made during implementation

- **Dead-token rule narrowed** (R-05): only an FcmError `UNREGISTERED`/`NOT_FOUND` deletes a token;
  a bare 404 does not, because a wrong project id answers 404 for every token. 401/403 abort the
  batch.
- **`SongLookup` port**: `SetlistService` depends on a one-method protocol
  (`get_songs_in_bulk`) instead of the whole `SongRepository`, so its unit tests need a small fake.
- **Wired container reachable from tests**: `AccountsConfig.container` keeps the one wired
  instance and the root `conftest.py` exposes it as the `di_container` fixture. Overriding a
  provider on the `Container` class does not reach the instance the views resolve from, so the
  API tests override `push_sender` and `clock` there.
- **Quiet loop**: `send_setlist_reminders` prints nothing and logs at debug level for
  `outside_window` (it runs every minute); `-v 2` prints it.

## Service split

| Unit | Responsibility |
|------|----------------|
| `core/domain/access.py` | + `codenames_at_least(scope, level)` |
| `core/domain/worship.py` (new) | `WORSHIP_MINISTRY_NAME`, `worship_name_pattern()` |
| `core/domain/push.py` (new) | `PushMessageType`, `PushMessage` |
| `core/domain/setlist_exceptions.py` (new) | four exceptions, re-exported |
| `core/repositories/access_repository.py` | + `user_ids_with_level` |
| `core/repositories/worship_repository.py` (new) | `is_worship_member`, `worship_member_user_ids`, `worship_ministry_exists` |
| `core/repositories/device_token_repository.py` (new) | `register`, `unregister`, `tokens_for(user_ids)`, `delete_tokens(tokens)` |
| `core/push/sender.py`, `fcm_sender.py`, `disabled_sender.py`, `factory.py` (new) | port, adapters, `build_push_sender(encoded_credentials)` |
| `core/application/access_service.py` | + `user_ids_with_level` passthrough |
| `core/application/worship_access_service.py` (new) | `flags_for`, `ensure_worship_member`, `setlist_recipients`, `reminder_recipients` |
| `core/application/push_service.py` (new) | `notify(user_ids, message) -> PushOutcome`: tokens → send → delete invalid → log → metric; never raises |
| `core/application/device_token_service.py` (new) | `register`, `unregister` with token validation |
| `core/http/permissions.py` | + `IsWorshipMember` |
| `features/accounts/views/devices.py` (new), `views/profile.py`, `serializers` | endpoints; flags in context and serializer |
| `features/songs/models/setlist.py` (new) | `Setlist`, `SetlistItem` |
| `features/songs/setlist_dtos.py` (new) | DTOs, `parse_setlist_items`, `parse_setlist_date` |
| `features/songs/services/setlist_rules.py` (new) | `ensure_sunday`, `ensure_unique_positions`, `current_reminder_slot` |
| `features/songs/repositories/setlist_repository.py` (new) + `interfaces.py` | `replace`, `get_by_date`, `current`, `pending`, `has_plays`, `claim_reminder_slot` |
| `features/songs/services/setlist_service.py` (new) | `save`, `current`, `by_date`, `pending` |
| `features/songs/services/setlist_reminder_service.py` (new) | `run() -> ReminderRunReport` |
| `features/songs/views/setlists.py` (new), `urls.py` | four endpoints |
| `features/songs/management/commands/send_setlist_reminders.py` (new) | one summary line, exit 0 |
| `config/di.py`, `config/settings/base.py` | providers (`push_sender` Singleton), wiring, env var |
| `compose.prod.yml`, `.env.example` | `ipbcb_setlist_reminder`; variable documented, empty |

## Implementation Order

Each step leaves the tree type-correct for the whole-tree mypy hook (memory: commit splitting).

0. **Specs** (with the first code step, CLAUDE.md §6.2): `specs/songs/spec.md` (Setlist,
   SetlistItem, four endpoints, reminder command, design decisions), `specs/accounts/spec.md`
   (device endpoints, `DeviceToken`, profile flags), `specs/members/spec.md` (the "Louvor" name is
   load-bearing: renaming it disables setlists), `tasks.md`.
1. **Access query**: `codenames_at_least`, `user_ids_with_level` + tests.
2. **Worship membership**: constant, repository, `WorshipAccessService`, `IsWorshipMember`,
   profile flags + tests.
3. **Push infrastructure**: `DeviceToken` + `core/0007`, repository, `DeviceTokenService`,
   device endpoints, push port/adapters/factory, `PushService`, settings variable, DI, metric +
   tests.
4. **Setlist**: models + `songs/0008`, DTOs, rules, repository, `SetlistService`, views, URLs,
   DI + tests.
5. **Reminder**: slot rule, `SetlistReminderService`, command, compose service, `.env.example` +
   tests.
6. Whole suite, mypy, ruff, `makemigrations --check`; quickstart §2–§3 locally; §4–§5 at deploy.

## Project Structure

### Documentation (this feature)

```text
specs/017-sunday-setlist-push/
├── spec.md
├── plan.md              # this file
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── setlist-api.md
│   ├── me-api.md
│   └── push-messages.md
├── checklists/requirements.md
└── tasks.md             # /speckit-tasks
```

### Source Code

```text
server/
├── config/
│   ├── di.py                                   # providers + wiring
│   └── settings/base.py                        # FCM_SERVICE_ACCOUNT_JSON_BASE64
├── core/
│   ├── application/{access_service,worship_access_service,push_service,device_token_service}.py
│   ├── domain/{access,worship,push,setlist_exceptions,exceptions}.py
│   ├── http/permissions.py                     # IsWorshipMember
│   ├── metrics.py                              # ipbcb_push_messages_total
│   ├── migrations/0007_devicetoken.py
│   ├── models/device_token.py
│   ├── push/{sender,fcm_sender,disabled_sender,factory}.py
│   ├── repositories/{access_repository,worship_repository,device_token_repository}.py
│   └── tests/{fakes.py, unit/, integration/}
└── features/
    ├── accounts/
    │   ├── views/{devices,profile}.py
    │   ├── serializers/serializers.py
    │   ├── urls.py
    │   └── tests/
    └── songs/
        ├── models/setlist.py
        ├── migrations/0008_setlist_setlistitem.py
        ├── setlist_dtos.py
        ├── repositories/{interfaces,setlist_repository}.py
        ├── services/{setlist_rules,setlist_service,setlist_reminder_service}.py
        ├── views/setlists.py
        ├── management/commands/send_setlist_reminders.py
        ├── urls.py
        └── tests/
compose.prod.yml                                # ipbcb_setlist_reminder
.env.example
```

**Structure Decision**: existing Django feature layout; no new app (R-01).

## Complexity Tracking

No constitution violations to justify.
