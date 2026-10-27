# Tasks: Rota Reminders by Push

**Input**: Design documents from `specs/024-schedule-reminders/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/push-messages.md

**Tests**: required by CLAUDE.md §10 (every new function gets a test; named fakes).

Paths are relative to `server/` unless they start with `specs/` or `../`.

## Phase 1: Setup

- [X] T001 Add the Reminders section (three kinds, windows, recipients, gating, claims, payload) to `../specs/schedule/spec.md`

## Phase 2: Foundational (blocks every story)

- [X] T002 [P] Add `SCHEDULE_WEEK`, `SCHEDULE_EVE`, `SCHEDULE_PUBLISHED` to `core/domain/push.py`
- [X] T003 Add `slots` and `month` to `PushMessage.as_data()` in `core/application/dtos/push_dtos.py`; log `push_month` in `core/application/push_service.py`; tests in `core/tests/`
- [X] T004 [P] Add `MemberAccountRepository` protocol to `core/repositories/interfaces.py` and `MemberAccountRepositoryImpl.user_ids_by_member` in `core/repositories/member_account_repository.py` (active user, profile linked, member access by flag or Admin/Liderança group; one query)
- [X] T005 [P] Add `FakeMemberAccountRepository` to `core/tests/fakes.py`; integration test for T004 in `core/tests/integration/test_member_account_repository.py`
- [X] T006 Create `features/schedule/services/reminder_rules.py`: `OVERWRITE_WINDOW`, `week_range`, `eve_date`, `publication_range`, `is_past_overwrite_window`, occasion keys, `slots_json`; use `OVERWRITE_WINDOW` in `features/schedule/services/schedule_service.py`; unit tests in `features/schedule/tests/unit/test_reminder_rules.py`
- [X] T007 Create `features/schedule/reminder_dtos.py` (`ReminderKind`, `RotaEntryDTO`, `RotaSlot`, `ReminderClaimKey`, `KindRunReport`, `ScheduleReminderRunReport`)
- [X] T008 Create `ScheduleReminderClaim` in `features/schedule/models/reminder_claim.py`, export it from `features/schedule/models/__init__.py`, generate `features/schedule/migrations/0004_*.py` with `makemigrations`
- [X] T009 Add `RotaReminderRepository` protocol to `features/schedule/repositories/interfaces.py` and `RotaReminderRepositoryImpl` (`entries_between`, `entries_of_month_from`, `months_first_saved_between`, `claim`) in `features/schedule/repositories/reminder_repository.py`; integration tests in `features/schedule/tests/integration/test_reminder_repository.py` (claim race via `run_id`, Subquery first save)
- [X] T010 Add `FakeRotaReminderRepository` and `FrozenClock` to `features/schedule/tests/fakes.py`
- [X] T011 Create `ScheduleReminderService` skeleton in `features/schedule/services/schedule_reminder_service.py` (shared: gate entries by overwrite window, group per member/occasion, resolve recipients, claim, notify, log)

## Phase 3: User Story 1 — Eve reminder (P1) 🎯 MVP

**Independent test**: Wednesday 18:59 nothing, 19:05 one `schedule_eve` with one slot, 19:30 nothing, Thursday 00:10 nothing.

- [X] T012 [US1] Implement the eve kind in `features/schedule/services/schedule_reminder_service.py`
- [X] T013 [US1] Unit tests in `features/schedule/tests/unit/test_schedule_reminder_service.py`: spec US1 scenarios 1–6, provider failure still claims, month inside overwrite window skipped
- [X] T014 [US1] Command `features/schedule/management/__init__.py`, `features/schedule/management/commands/__init__.py`, `features/schedule/management/commands/send_schedule_reminders.py` with `summary_line`; providers and wiring in `config/di.py`
- [X] T015 [US1] Integration test `features/schedule/tests/integration/test_send_schedule_reminders_command.py`

## Phase 4: User Story 2 — Monday week summary (P2)

**Independent test**: Monday 08:03 one `schedule_week` with Tuesday and Sunday slots in order; member without entries gets nothing; Tuesday run sends nothing.

- [X] T016 [US2] Implement the week kind in `features/schedule/services/schedule_reminder_service.py`
- [X] T017 [US2] Unit tests for US2 scenarios 1–6 in `features/schedule/tests/unit/test_schedule_reminder_service.py`

## Phase 5: User Story 3 — Publication (P2)

**Independent test**: month first saved 10:00; 10:20 nothing; 10:31 one `schedule_published` per member with `month` and future entries; next day nothing.

- [X] T018 [US3] Implement the publication kind in `features/schedule/services/schedule_reminder_service.py`
- [X] T019 [US3] Unit tests for US3 scenarios 1–6 in `features/schedule/tests/unit/test_schedule_reminder_service.py`

## Phase 6: Polish

- [X] T020 Add `python manage.py send_schedule_reminders` to the `ipbcb_setlist_reminder` loop and update its comment in `../compose.prod.yml`
- [X] T021 Run `pytest features/schedule core`, then the full suite, then pre-commit (black, ruff, mypy, bandit)
- [X] T022 Mark this file's tasks done and check `../specs/schedule/spec.md` matches the code

## Dependencies

- T001 first (spec before code). T002–T011 before any story.
- US1 → US2 → US3 touch the same service file, so sequential; each is testable alone once Phase 2 is done.
- T020–T022 last.

## Parallel examples

- T002, T004, T005 (different files) together; T006 and T007 together after T002.

## Implementation strategy

MVP = Phase 2 + US1 (eve reminder) — the forgetfulness the feature fixes. Then US2, US3, polish.
