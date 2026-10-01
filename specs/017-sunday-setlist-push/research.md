# Research: Sunday Worship Setlist with Push Distribution

Decisions behind [plan.md](plan.md). Each entry: decision, rationale, alternatives.

---

## R-01 — Where each piece lives

**Decision**:

| Piece | Home | Why there |
|-------|------|-----------|
| `Setlist`, `SetlistItem`, save/read/pending services, reminder service and command | `features/songs` | Setlists reference `Song` and the reminder reads `Played`; both are songs models |
| `DeviceToken` model, push sender, `PushService`, `DeviceTokenService` | `core` | Shared: tokens are registered from `accounts` and pushes are sent from `songs` |
| Worship membership query and the worship flags | `core` | Read by `accounts` (profile flags) and `songs` (save, current read, recipients) |
| Device registration endpoints | `features/accounts` (`api/me/devices/`) | Per-user, next to `api/me/profile/`; the app calls them around login/logout |

**Rationale**: the constitution forbids features importing each other and admits a model in
`core` only when two or more features use it. `DeviceToken` is written by `accounts` and read by
`songs`, so it qualifies. The worship membership query traverses
`User → profile → member → ministries` by lookup strings, the same way `Profile.member` names
`"members.Member"` without importing it.

**Alternatives**:
- A new `features/notifications` app owning tokens and sending: `songs` would then import it,
  which the constitution forbids; a port wired in `config/di.py` would work but adds a feature
  and an adapter for what is one model and one service.
- Device endpoints in `songs`: tokens are not about songs, and later pushes (events, notices)
  would have to reach into `songs` to find them.

---

## R-02 — Authorization

**Decision**:

| Endpoint | Permission classes | Extra check in the service |
|----------|--------------------|----------------------------|
| `PUT api/setlists/{date}/` | `IsAuthenticated`, `scope_permission(Scope.SONGS)` (PUT → `manage`) | caller is a worship member, else `NotWorshipMemberError` (403) |
| `GET api/setlists/{date}/` | same class with `{"GET": Level.MANAGE}` override | — |
| `GET api/setlists/pending-confirmation/` | `IsAuthenticated`, `scope_permission(Scope.SONGS, {"GET": Level.MANAGE})` | — |
| `GET api/setlists/current/` | `IsAuthenticated`, `IsWorshipMember` (new, `core.http.permissions`) | — |
| `POST api/me/devices/`, `POST api/me/devices/unregister/` | `IsAuthenticated` | — |

`PUT` and `GET` on `{date}` share one view, so one class carries the `GET` override; the `PUT`
default is already `manage`.

**Rationale**: clarification Q1 — levels only through scopes. The worship check stays in the
service rather than a second permission class on the `PUT`, because the same rule is reused by
`can_save_setlist` and by reminder recipients, and the service is where it is unit-tested with a
fake. `current/` is not a management endpoint (the band reads it, not the panel), so it is gated
by membership like `IsMemberUser`, not by a scope; worship membership never grants a level.

**Alternatives**: a `scope_permission` on `current/` too (`view` on `songs`) — would exclude
every worship member without a role, i.e. most of the band.

---

## R-03 — Worship membership query

**Decision**: `core/domain/worship.py` holds `WORSHIP_MINISTRY_NAME = "Louvor"`. The repository
matches it with `profile__member__ministries__name__iregex=r"^\s*louvor\s*$"` built from
`re.escape` of the constant, on `get_user_model()`, `is_active=True`, `.distinct()`. Two queries
are exposed: `is_worship_member(user_id) -> bool` and `worship_member_user_ids() -> set[UUID]`,
plus `worship_ministry_exists() -> bool` for the rename warning.

**Rationale**: the spec compares case-insensitively and ignoring surrounding whitespace;
`iexact` does not trim, and a `Trim`/`Lower` annotation across the M2M join is harder to read.
`iregex` runs on PostgreSQL and SQLite (tests) alike. Inactive users are excluded: they cannot
log in, and their tokens would only waste sends.

`Member.is_active` ("valid profile") is **not** filtered (plan OQ-1, answered A).

**Alternatives**: looking up the ministry id first by name, then filtering by id — two queries
for no gain; matching by id — rejected by the spec.

---

## R-04 — Who holds `manage` on `songs` (reminder recipients)

**Decision**: `core.domain.access` gains `codenames_at_least(scope, level) -> frozenset[str]`
(e.g. `songs__manage`, `songs__owner`). `RoleGrantRepositoryImpl` gains
`user_ids_with_level(scope, level) -> set[UUID]`: active users in the Admin group, union active
users in a role group holding one of those codenames on `core.PanelScope`. `AccessService`
exposes it unchanged. Recipients = that set ∩ `worship_member_user_ids()`.

**Rationale**: mirrors `resolve_grants` (Admin is owner of every scope without stored rows;
other roles through their codenames, role groups only) as a set query instead of per user, so
the reminder run is two queries, not one per user (constitution: no queries in loops). The
pure function keeps the "levels are hierarchical" rule in the domain, next to `resolve_grants`.

**Alternatives**: iterate users calling `grants_for` — N queries per run.

---

## R-05 — Push transport (FCM HTTP v1)

**Decision**: `core/push/` holds a project-owned port and two adapters.

- `PushSender` (Protocol): `send(tokens: Sequence[str], message: PushMessage) -> PushSendReport`
  where the report carries `sent`, `invalid_tokens`, `failed`, `aborted: bool`.
- `FcmPushSender`: `google.oauth2.service_account.Credentials.from_service_account_info(...,
  scopes=["https://www.googleapis.com/auth/firebase.messaging"])` and
  `google.auth.transport.requests.AuthorizedSession`, which refreshes the OAuth token itself.
  One `POST https://fcm.googleapis.com/v1/projects/{project_id}/messages:send` per token
  (v1 has no multicast), body
  `{"message": {"token": t, "data": {"type": ..., "date": ...}, "android": {"priority": "HIGH"}}}`.
  `project_id` comes from the service account JSON.
- `DisabledPushSender`: used when credentials are absent; sends nothing and reports every token
  as skipped, so the caller logs `push_disabled`.
- Built once (`providers.Singleton`) so the OAuth token (1 h) and the HTTP connection are reused.

Response handling, per token:

| FCM answer | Outcome |
|------------|---------|
| 200 | sent |
| `errorCode` `UNREGISTERED` / `NOT_FOUND` in `error.details` (FcmError) | `invalid_tokens` (deleted by `PushService`) |
| 401 / 403 | `aborted`: credentials or project are wrong, every remaining token would fail the same way |
| any other status, **including a bare 404** | `failed`, token kept |
| connection error / timeout / OAuth refresh failure | `aborted`: stop the batch, remaining tokens counted as failed |

A bare 404 is not taken as a dead token (changed during implementation): a wrong `project_id`
answers 404 for every token, and deleting on it would wipe the whole table.

Timeouts `(3.05, 5)` seconds (connect, read).

**Rationale**: the request names google-auth + requests, both already pinned. `HIGH` priority
because a data-only message at normal priority can be held for a dozing phone, which would break
SC-001. Aborting on a transport error is what keeps SC-002 when the provider is down: without it
a 30-device send would wait 30 × 3 s. `INVALID_ARGUMENT` is not treated as an invalid token: it
also means a malformed payload, and deleting every token on a payload bug would wipe the table.

**Alternatives**: `firebase-admin` — a new, large dependency for one HTTP call; legacy FCM API —
shut down by Google.

---

## R-06 — Credentials

**Decision**: `FCM_SERVICE_ACCOUNT_JSON_BASE64` in `.env`: the service account JSON, base64
encoded on one line. Read in `config/settings/base.py` with default `""`; decoding and parsing
happen in the sender factory, and a value that does not decode or lacks `project_id` /
`client_email` / `private_key` raises `ImproperlyConfigured` at first use with the missing key
named (never the value). Empty means disabled. Chosen in plan OQ-2 (answer A).

**Rationale**: the request requires an environment variable. A raw multi-line JSON does not fit a
`.env` line; base64 does, and needs no volume or file permission in either container.

**Alternatives**: a mounted key file with its path in the variable (`GOOGLE_APPLICATION_CREDENTIALS`
style) — a second secret location outside `.env`, a volume in two compose services, and file
permissions to get right.

---

## R-07 — Sending after a save

**Decision**: `SetlistService.save` commits the replacement (repository, inside
`transaction.atomic`), then calls `PushService.notify(user_ids, message)` outside the
transaction. `PushService` catches every sender exception, logs it, and returns a report — it
never raises. The view answers after the send returns.

**Rationale**: spec assumption accepted by the user: synchronous, after commit. A push sent
before commit could announce a setlist a rollback then removes. The worship ministry is tens of
devices; at ~50–100 ms per FCM call on a reused connection that is 1–3 s, inside SC-002 only at the
low end — the quickstart measures it on production-size data, and a breach reopens this decision
(outbox drained by the reminder loop is the fallback).

**Alternatives**: `transaction.on_commit` — same effect here since the service owns the
transaction; a background thread — loses the error inside a gunicorn worker and is invisible to
tests; outbox — more moving parts than the measured need.

---

## R-08 — Saving: replace and concurrency

**Decision**: `SetlistRepositoryImpl.replace(date, author_id, items)` inside
`transaction.atomic()`: `get_or_create(date=...)` (Django retries the get on the unique-violation
race), `select_for_update()` on that row, delete its items, `bulk_create` the new ones, update
`saved_by` and `saved_at` (from the injected clock). `last_reminder_slot` is left untouched: a
correction saved at 22:10 must not re-send the 21:00–22:00 windows. Returns the stored setlist DTO with items joined to songs in one query.

**Rationale**: FR-006 atomic replacement; the row lock serializes two concurrent saves of the same
date so the result is entirely one or the other (edge case). SQLite ignores `select_for_update`
but serializes writes anyway.

**Alternatives**: `update_or_create` — no hook to delete the items under the same lock.

---

## R-09 — Validation

**Decision**: `features/songs/setlist_dtos.py`:
`parse_setlist_input(payload) -> list[SetlistItemInput]` after `require_object_body`; date from
the URL parsed by a helper raising `ValidationError` naming the value and `YYYY-MM-DD`.
Pure rules in `features/songs/services/setlist_rules.py`: `ensure_sunday(date)`,
`ensure_unique_positions(items)`. Item rules: `song_id` and `position` via `require_int`,
position 1–10, `tone` stripped string 1–3 characters. Missing songs → existing
`SongsNotFoundError` (404) from the service, before any write.

Order: scope permission (403) → view parses body and date (400) → service: worship membership
(403) → Sunday and unique positions (400) → songs exist (404) → write. A non-member with a
malformed body therefore gets `400`; nothing about the setlist leaks either way, so the order
follows the existing layering (shape in the view, rules in the service).

**Rationale**: matches the `register_plays` parsing style and the constitution's parsing guards.

---

## R-10 — Reminder windows and deduplication

**Decision**: pure function `current_reminder_slot(now_local: datetime) -> datetime | None` in
`setlist_rules.py`: `None` unless Sunday and `21:00 <= time`; otherwise the start of the current
half hour (`minute // 30 * 30`). `SetlistReminderService.run()`:

1. `now_local = timezone.localtime(clock.now())` (TIME_ZONE is `America/Sao_Paulo`).
2. slot = `current_reminder_slot(now_local)`; none → `skipped: outside_window`.
3. setlist for `now_local.date()`; none → `skipped: no_setlist`.
4. plays registered for the date → `skipped: confirmed`.
5. `claim_reminder_slot(setlist_id, slot)`: one conditional `UPDATE … SET last_reminder_slot=slot
   WHERE id=… AND (last_reminder_slot IS NULL OR last_reminder_slot < slot)`; 0 rows →
   `skipped: already_sent`.
6. recipients (R-04) → `PushService.notify(..., confirm_plays)`; outcome logged.

**Rationale**: the claim happens before the send, so a failed send still consumes the window
(FR-020) and two overlapping runs cannot both send (FR-018). Only the current slot is ever
computed, so missed windows are never sent late (FR-019).

**Alternatives**: a separate `ReminderLog` table with one row per window — more rows for the same
guarantee; storing it on the setlist keeps the rule next to its subject.

---

## R-11 — Scheduling

**Decision**: compose service `ipbcb_setlist_reminder`, cloned from `ipbcb_token_flush`:
`while true; do python manage.py send_setlist_reminders; sleep 60; done`, same image, `./.env`,
pinned `DJANGO_ENV`/`DJANGO_SETTINGS_MODULE`, `depends_on` db healthy and server started. The
command prints one summary line and always exits 0.

**Rationale**: request — follow the token flush pattern, no Celery. 60 s keeps each window's send
within its first two minutes. Outside Sunday 21:00–24:00 a run exits after computing that no slot
applies, without a query; inside it, a run is at most four cheap queries plus the send.

**Alternatives**: one long-running command with an internal loop — reuses Django boot, but a
crash inside it would stop reminders until the restart policy kicks in, and it diverges from the
existing pattern.

---

## R-12 — Current setlist and pending confirmation queries

**Decision**:
- current: `Setlist.objects.filter(date__gte=today).order_by("date").first()`, items prefetched.
- pending: setlists with `date__lte=today` and `~Exists(Played.objects.filter(date=OuterRef("date")))`,
  ordered `-date`, items with songs prefetched. One query plus one prefetch.
- today = `timezone.localdate(clock.now())`.

**Rationale**: no queries in loops; `Exists` keeps it a single SQL statement on both backends.

---

## R-13 — Profile flags

**Decision**: `WorshipAccessService.flags_for(user_id, grants) -> WorshipFlagsDTO(is_worship_member,
can_save_setlist)`; the profile view already computes `grants` and passes both into the serializer
context; `ProfileSerializer` gains two read-only fields with the same "no silent default" guard.
The ETag is computed from the body, so it changes with the flags automatically.

---

## R-14 — Device token registration

**Decision**: `DeviceTokenRepositoryImpl.register(user_id, token)`: `update_or_create(token=…,
defaults={"user_id": user_id})` — moves an existing token to the caller. `unregister(user_id,
token)`: `filter(token=…, user_id=…).delete()`. Token validated: string, stripped, 1–512
characters, no whitespace inside. `POST` for both (unregister at `api/me/devices/unregister/`):
the token is long and must not appear in a URL (access logs).

**Rationale**: FR-013/014. A `DELETE` with a body is legal but awkward for Retrofit and some
proxies; `POST …/unregister/` mirrors `api/auth/logout/`.

---

## R-15 — Logging and metrics

**Decision**: structured log events (spec 002 format, ids only, never member fields or tokens):

| Event | Level | Fields |
|-------|-------|--------|
| `setlist_saved` | info | `setlist_date`, `user_id`, `item_count`, `replaced` |
| `push_sent` | info | `push_type`, `push_date`, `recipients`, `devices`, `sent`, `failed`, `invalid_removed`, `aborted` |
| `push_disabled` | warning | `push_type`, `devices` |
| `push_transport_error` | warning | `push_type`, `error_class` |
| `worship_ministry_missing` | warning | `ministry_name` |
| `setlist_reminder_run` | info (debug for `outside_window`) | `outcome`, `setlist_date`, `slot` |

Metric `ipbcb_push_messages_total{type, outcome}` in `core.metrics`, incremented by the server
process only (the reminder container is not scraped; its logs are the record).

**Rationale**: constitution (members data: `member_id`/ids only). Tokens are credentials to a
device and stay out of logs.
