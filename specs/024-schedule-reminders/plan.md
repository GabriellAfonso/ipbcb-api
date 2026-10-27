# Implementation Plan: Rota Reminders by Push

**Branch**: `024-schedule-reminders` | **Date**: 2026-10-27 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/024-schedule-reminders/spec.md`

## Summary

`schedule` gains `ScheduleReminderClaim` and a `ScheduleReminderService` run every 60 s by a new
`send_schedule_reminders` command, added to the existing `ipbcb_setlist_reminder` loop. Each run
computes, from local time, which of the three occasions are open now — the Monday week summary
(from 08:00), the eve reminder for tomorrow's entries (from 19:00), and the publication of months
whose first save + 30 min fell today and has passed — reads the matching rota entries (only of
months past their overwrite window), resolves each member to their linked user with member access,
claims `(kind, member, occasion)` in one bulk insert tagged with a run id, and sends one data push
per claimed member with that member's slots as a JSON string. `PushMessage` gains `slots` and
`month`; `core` gains a member → user lookup.

## Technical Context

**Language/Version**: Python 3.14, `.venv_windows`

**Primary Dependencies**: Django 6.0, DRF 3.17, dependency-injector, Pydantic 2.12. No new
dependency.

**Storage**: PostgreSQL in production, SQLite in tests. Generated migration `schedule/0004`
(one `CreateModel`). No data migration.

**Testing**: pytest + pytest-django; named fakes (`FakeRotaReminderRepository`,
`FakeMemberAccountRepository`, existing `FakePushSender`, `FakeDeviceTokenRepository`,
`FrozenClock`); mypy, ruff, bandit via pre-commit.

**Target Platform**: Linux containers behind nginx; the existing `ipbcb_setlist_reminder` loop.

**Project Type**: Web service (REST API), single Android client. No new endpoint.

**Performance Goals**: each occasion sent within ~1 min of opening (loop period); a run outside
every window costs three cheap queries.

**Constraints**: no task queue; features never import each other (members/accounts by lookup
strings); ORM only in repositories; no queries in loops except one `notify` per member (R-07);
files < 500 lines, functions 4–20 lines.

**Scale/Scope**: ~18 rota members, ~13 entries a month, 3 services; 1 model, 1 command.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design; result unchanged.*

| Rule (`specs/constitution.md`, `CLAUDE.md`) | Status |
|---|---|
| Features never import each other | ✅ member → user in `core` by lookup strings (R-03); `schedule` imports only `core` |
| `core` models only if shared | ✅ no new core model; the claim lives in `schedule` |
| Views → services → repositories; ORM only in repositories | ✅ no view; command → service → repositories |
| Services never import HTTP | ✅ |
| No queries in loops | ✅ claims bulk (R-02), recipients one query (R-03), entries one query; `notify` per member justified in Complexity Tracking |
| DI via `config/di.py`; Pydantic DTOs | ✅ |
| Members data sensitive: ids only in logs; push carries no person data | ✅ payload has catalogue data only (spec, Payload); logs carry kind, occasion, counts |
| Domain exceptions with offending value | ✅ none raised; the run never fails |
| Migrations generated | ✅ `makemigrations` |
| Models: `__str__`, `Meta.ordering`, `verbose_name` | ✅ data-model |
| No hardcoded secrets | ✅ reuses `FCM_SERVICE_ACCOUNT_JSON_BASE64` already in the loop's `.env` |
| Spec before code, same commit | ✅ `specs/schedule/spec.md` updated in the implementation commit |

Gate: **pass**.

## Technical Decisions

See [research.md](research.md): claims table and occasion keys (R-01), race-free bulk claim with a
run id (R-02), recipients (R-03), shared `OVERWRITE_WINDOW` and gating (R-04), windows (R-05),
payload (R-06), one `notify` per member (R-07), reuse of the existing loop (R-08), no claim
without a recipient (R-09).

### Run flow

```
run():
  now = localtime(clock.now())
  for each kind whose window is open now (rules):
      entries  = repository.<kind entries>(...)  filtered to month_first_saved_at + 30 min <= now
      groups   = per (member, occasion) → slots
      users    = members.user_ids_by_member(member ids)        # drop members without a user
      won      = repository.claim(kind, keys, run_id)           # before sending
      for key in won: push.notify({users[key.member]}, message(kind, occasion, slots))
  log one line per kind; return report
```

Order of kinds within a run: publication, week, eve — so on a Monday when a month is published,
the broad message comes first.

### Implementation order

1. Spec: `specs/schedule/spec.md` gains the Reminders section.
2. `core`: `PushMessageType` values, `PushMessage.slots/month`, `push_month` log field;
   `MemberAccountRepository` + fake + tests; DI.
3. `schedule`: `reminder_rules.py` (windows, `OVERWRITE_WINDOW`, `slots_json`, occasion keys) +
   unit tests; `ScheduleService` uses `OVERWRITE_WINDOW`.
4. `schedule`: model + migration; `RotaReminderRepository` protocol + impl + integration tests.
5. `schedule`: `ScheduleReminderService` + unit tests with fakes.
6. Command + DI wiring + integration test; `compose.prod.yml` loop line.
7. Full suite, pre-commit.

## Project Structure

### Documentation (this feature)

```text
specs/024-schedule-reminders/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/push-messages.md
└── tasks.md
```

### Source Code

```text
server/
├── core/
│   ├── domain/push.py                              # + 3 message types
│   ├── application/dtos/push_dtos.py               # + slots, month
│   ├── application/push_service.py                 # + push_month log field
│   ├── repositories/interfaces.py                  # + MemberAccountRepository
│   ├── repositories/member_account_repository.py   # new
│   └── tests/fakes.py                              # + FakeMemberAccountRepository
├── features/schedule/
│   ├── models/reminder_claim.py                    # new ScheduleReminderClaim
│   ├── migrations/0004_*.py                        # generated
│   ├── reminder_dtos.py                            # new
│   ├── repositories/interfaces.py                  # + RotaReminderRepository
│   ├── repositories/reminder_repository.py         # new
│   ├── services/reminder_rules.py                  # new, pure
│   ├── services/schedule_reminder_service.py       # new
│   ├── services/schedule_service.py                # uses OVERWRITE_WINDOW
│   ├── management/commands/send_schedule_reminders.py
│   └── tests/{fakes.py, unit/..., integration/...}
├── config/di.py                                    # providers + wiring
└── ../compose.prod.yml                             # loop line
```

**Structure Decision**: everything rota-specific stays in `features/schedule`; only the member →
user lookup goes to `core`, because it crosses into `accounts` and `members`.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| One `PushService.notify` (token query + provider call) per claimed member | Each member's message carries their own slots (FR-003); `notify` sends one message to a set of users | A batched multi-message `notify` adds API for at most ~18 calls on a Monday |
