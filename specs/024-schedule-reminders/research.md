# Research: Rota Reminders by Push

All decisions below were taken against the code on 2026-10-27. No open question remains.

## R-01 — Where the claims live

- **Decision**: a new model `schedule.ScheduleReminderClaim(kind, member, occasion, run_id,
  claimed_at)`, unique on `(kind, member, occasion)`. `occasion` is a string key: the Monday's ISO
  date for the week summary (`2026-10-26`), `"<date>/<service id>"` for an eve reminder
  (`2026-10-29/3`), `YYYY-MM` for the publication (`2026-11`).
- **Rationale**: one table serves the three kinds. The eve key uses `(date, service)`, not the
  `MonthlySchedule` row id, because a save replaces every row of the month (delete + bulk create)
  and the ids change; `(service, date)` is the rota's own unique key, so it survives.
- **Alternatives**: a field on `MonthlySchedule` (as `Setlist.last_reminder_slot`) — covers the eve
  reminder only, and would be lost if the month were ever replaced; the week summary and the
  publication are per member, not per row. A nullable FK to the service plus a date — Postgres
  treats NULLs as distinct in unique constraints, so the week/publication rows would never collide.

## R-02 — Claiming without a query per member

- **Decision**: per kind and run, insert every wanted `(kind, member, occasion)` in one
  `bulk_create(ignore_conflicts=True)` carrying a fresh `run_id` (UUID), then read back the rows
  with that `run_id`. Those, and only those, are this run's to send.
- **Rationale**: the claim is made before the push (FR-013) and two overlapping runs can never both
  win a row — the unique constraint decides. `ignore_conflicts` does not say which rows were
  inserted, so the `run_id` tells them apart. Two queries per kind, not one per member
  (constitution: no queries inside loops).
- **Alternatives**: `create()` per member catching `IntegrityError` (the 017 pattern for its single
  row) — one query per member. Select-then-insert — races between overlapping runs.

## R-03 — Recipients

- **Decision**: a new core repository `MemberAccountRepository.user_ids_by_member(member_ids) ->
  dict[int, UUID]`: active users whose `profile__member_id` is in the set **and** who have member
  access (`profile__member_access` or a group in `MEMBER_ACCESS_ROLES`). One query, lookup strings
  only, like `WorshipMembershipRepositoryImpl`.
- **Rationale**: `schedule` may not import `accounts` (constitution); member access is defined in
  `core.domain.access`; the profile is one-to-one with the member, so one user per member at most.
- **Alternatives**: reuse `HasMemberAccess` — it works on a request, not on a set of users.

## R-04 — Publication moment and gating (FR-009–FR-012, FR-019)

- **Decision**: extract `OVERWRITE_WINDOW = timedelta(minutes=30)` into
  `features/schedule/services/reminder_rules.py` and use it in `ScheduleService.save_schedule` too.
  The repository returns each rota entry with its month's earliest `created_at` (a `Subquery`), and
  lists months whose earliest `created_at` falls in `(today_start − 30 min, now − 30 min]` — i.e.
  whose publication moment is today and past.
- **Rationale**: one definition of the window for the 409 rule and the reminders, so they cannot
  drift. Gating the week summary and the eve reminder on the same moment keeps the promise that
  nothing is sent from a rota that can still change.
- **Alternatives**: a `published_at` column set by the save — needs a migration on
  `MonthlySchedule` and a data backfill, for a value the existing `created_at` already gives.

## R-05 — Time windows (FR-004, FR-006, FR-007, FR-014)

- **Decision**: pure functions on local time (`timezone.localtime(clock.now())`):
  - week: Monday and `now ≥ 08:00` → `(monday, monday + 6 days)`, else none;
  - eve: `now ≥ 19:00` → `today + 1 day`, else none;
  - publication: `[today 00:00, now]` for the moment.
  Each window ends at midnight, so a run on a later day never finds yesterday's occasion.
- **Rationale**: same approach as `current_reminder_window` (017): only the current window is ever
  computed, which is what makes missed occasions vanish at midnight without extra state.

## R-06 — Payload

- **Decision**: `PushMessage` gains `slots: str | None` and `month: str | None`, emitted by
  `as_data()` when set. `slots` is built by `slots_json()`: `json.dumps(..., ensure_ascii=False,
  separators=(",", ":"))` of `[{date, service, time}]` sorted by date then time. Three new
  `PushMessageType` values. `PushService` is unchanged except logging `push_month` when present;
  slots are never logged.
- **Rationale**: FCM data values must be strings; the app parses the string as JSON. Keeping the
  encoding in one function makes the wire format testable.

## R-07 — One `notify` per member

- **Decision**: `PushService.notify({user_id}, message)` once per claimed member/occasion.
- **Rationale**: each message carries that member's own slots (FR-003), and `notify` sends one
  message to a set of users. At ~18 rota members it is at most ~18 calls on a Monday; each call
  already does its own token query and provider request.
- **Alternatives**: a batched multi-message send in `PushService` — new API for a few calls a day.

## R-08 — Where it runs

- **Decision**: command `send_schedule_reminders` in `features/schedule/management/commands/`,
  added to the existing `ipbcb_setlist_reminder` loop in `compose.prod.yml` (one more line before
  `sleep 60`).
- **Rationale**: same cadence, same image, same secrets; another container would duplicate the
  block for nothing. The container name stays to avoid touching the deploy; its comment is updated.
- **Alternatives**: a new `ipbcb_schedule_reminder` container — more config, no isolation benefit
  (each command exits 0 and is independent).

## R-09 — Claims for members without recipients

- **Decision**: a member with no recipient user is not claimed (nothing is sent, nothing recorded);
  a member with a recipient but no device is claimed and `notify` finds no token.
- **Rationale**: if the leader links the profile later the same day, the member still gets the
  reminder inside the window. The device case is recorded, as in the spec's edge cases.
