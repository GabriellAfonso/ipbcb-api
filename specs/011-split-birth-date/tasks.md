---

description: "Task list for Split Member Birth Date into Day, Month and Year"
---

# Tasks: Split Member Birth Date into Day, Month and Year

**Input**: Design documents from `specs/011-split-birth-date/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/admin-members-api.md,
quickstart.md

**Tests**: Included. CLAUDE.md §10 requires a test for every new function, and spec FR-019
requires a test for each validation rule and conversion case. Fakes are the named classes in
`server/features/members/tests/fakes.py`.

**Organization**: Tasks are grouped by user story. All paths are relative to the repository
root. Run commands from `server/` with `.venv_windows` active (PowerShell).

**Commit rule**: the mypy pre-commit hook checks the whole tree, so every commit must leave it
type-correct. `birth_date` stays on the model until Phase 7, so phases 2–6 can land one by one.
Tasks marked **(commit group A)** change the leader DTOs and every reader of them: they land in
one commit.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1–US5 from spec.md

---

## Phase 1: Setup

**Purpose**: Known-green baseline before touching the schema.

- [X] T001 Run `pytest features/members` and `mypy .` from `server/` and confirm both pass on branch `011-split-birth-date` before any change

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: New columns, database constraints, the pure validation rules and history
rendering for integers. Everything here is additive: `birth_date` and `validate_member_dates`
keep working, so each task leaves the tree green.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T002 In `server/features/members/domain/member_dates.py` add a frozen dataclass `BirthDateParts(day: int | None, month: int | None, year: int | None)` and a public `validate_member_date_parts(birth: BirthDateParts, baptism_date: date | None, today: date) -> None` implementing, in this order (research R-03): range (day 1-31, month 1-12, year 1-9999); day and month both set or both empty; calendar validity via `calendar.monthrange(year or 2000, month)[1]` (29/02 passes with no year or a leap year, fails with a non-leap year); future (`year > today.year`, or full `date(year, month, day) > today`; day+month alone never future); baptism not in the future (reuse `_reject_future`); baptism before birth (full date vs `baptism_date`; year-only vs `baptism_date.year`; no check with day+month only). Each rule is its own private helper of 4-20 lines. Each raises `core.domain.exceptions.ValidationError` with a Portuguese message naming the offending value(s) and the expected shape, e.g. `"Dia de nascimento sem mês: birth_day=12, birth_month=None. Envie os dois ou nenhum."`. Docstring with intent and one usage example. Keep the existing `validate_member_dates` untouched
- [X] T003 [P] In `server/features/members/tests/unit/test_member_dates.py` add `class TestValidateMemberDateParts` with `TODAY = date(2026, 9, 28)`: parametrized rejections for every "Rejected example" row of `specs/011-split-birth-date/data-model.md` (Validation rules), each asserting via `match=` that the offending value is in the message; parametrized acceptances for every "Accepted example" row plus the four valid states (full, day+month, year only, nothing); 29/02 with year None, 2000 (accepted) and 1990 (rejected); `BirthDateParts(1, 10, None)` accepted with `TODAY` (day+month never future); birth year 1990 with baptism 1989-12-31 rejected and 1990-01-01 accepted; day+month only with any baptism accepted
- [X] T004 [P] In `server/features/members/domain/member_changes.py` add `int` to `HistoryValue` and an `int` branch in `render_history_value` placed after the `bool` branch (`bool` is an `int` subclass) returning `str(value)`; do not change `HISTORY_FIELDS` yet. In `server/features/members/tests/unit/test_member_changes.py` add cases to `test_renders_each_value_type`: `12 -> "12"`, `1990 -> "1990"`, and keep `True -> "true"`
- [X] T005 In `server/features/members/models/member.py` add `birth_day`, `birth_month`, `birth_year` as `models.PositiveSmallIntegerField(null=True, blank=True)` next to `birth_date` (keep `birth_date` for now), with a comment saying why the date is split (partial dates; no placeholder year; spec 011). Add `class Meta` on `Member` with `constraints` = three `models.CheckConstraint`s named `member_birth_day_month_together` (`Q(birth_day__isnull=True, birth_month__isnull=True) | Q(birth_day__isnull=False, birth_month__isnull=False)`), `member_birth_day_range` (`Q(birth_day__isnull=True) | Q(birth_day__gte=1, birth_day__lte=31)`), `member_birth_month_range` (`Q(birth_month__isnull=True) | Q(birth_month__gte=1, birth_month__lte=12)`). Use the Django 6 `condition=` keyword. Do not add `ordering`/`verbose_name` (plan, Constitution Check)
- [X] T006 Run `python manage.py makemigrations members` from `server/` and keep the generated `server/features/members/migrations/0004_*.py` unedited (adds three fields + three constraints). Run `python manage.py makemigrations --check --dry-run` afterwards to confirm nothing is pending
- [X] T007 [P] Create `server/features/members/tests/integration/test_member_constraints.py` (`@pytest.mark.django_db`): `Member.objects.create` with `birth_day=12, birth_month=None` raises `IntegrityError` (wrap in `transaction.atomic()`); same for `birth_day=None, birth_month=3`; `birth_day=32` and `birth_month=13` raise `IntegrityError`; `birth_day=12, birth_month=3, birth_year=None` and `birth_year=1950` alone are stored; `Member(name="x", birth_day=12).full_clean()` raises Django `ValidationError` naming `member_birth_day_month_together` (proves the Django admin form sees the constraint, research R-01)

**Checkpoint**: New columns exist and are guarded; validation rules are tested in isolation.

---

## Phase 3: User Story 4 - Existing records are converted without data entry (Priority: P1)

**Goal**: Every existing `birth_date` is copied into the three parts, with year 1 read as
"unknown"; the conversion refuses to run backwards.

**Independent Test**: With rows migrated to 0004, create members with `1990-03-12`,
`0001-07-25` and no date, apply 0005, and check the parts; then try to migrate back to 0004.

- [X] T008 [US4] Create hand-written `server/features/members/migrations/0005_split_birth_date.py` depending on the generated 0004. Top-of-file docstring (CLAUDE.md §5) stating: why (a single date could not hold partial dates; year 0001 was an undocumented "year unknown" placeholder; year-only could not be stored), what (copy day and month; copy year unless it is 1, then null), that it is irreversible on purpose (spec FR-015, recovery is the pre-deploy dump), and that it was verified against a restored production dump (quickstart §2). Body: a `forward(apps, schema_editor)` function using `apps.get_model("members", "Member")` and one `filter(birth_date__isnull=False).update(birth_day=ExtractDay("birth_date"), birth_month=ExtractMonth("birth_date"), birth_year=Case(When(birth_date__year=1, then=Value(None)), default=ExtractYear("birth_date")))` (research R-02); `operations = [migrations.RunPython(forward)]` with **no** `reverse_code`
- [X] T009 [US4] Create `server/features/members/tests/integration/test_birth_date_split_migration.py` using `django.db.migrations.executor.MigrationExecutor` (mark `@pytest.mark.django_db(transaction=True)`): migrate to `("members", "0004_…")`, create three rows through the historical model (`1990-03-12`, `0001-07-25`, null), migrate to `0005_split_birth_date`, assert `(12, 3, 1990)`, `(25, 7, None)`, `(None, None, None)`; a second test asserts that migrating from 0005 back to 0004 raises `django.db.migrations.exceptions.IrreversibleError`; finally migrate forward to the latest state so later tests see the full schema

**Checkpoint**: Conversion proven on the test database; ready for the dump check in Phase 8.

---

## Phase 4: User Story 1 - Leader records a partially known birth date (Priority: P1) 🎯 MVP

**Goal**: The leader endpoints read and write `birth_day`, `birth_month`, `birth_year` instead
of `birth_date`, and the service validates the record as it would be after the write.

**Independent Test**: As a leader, create one member per valid state (full, day+month,
year only, nothing), clear only the year of a full date, add day+month to a year-only member,
and read each record back (spec US1 scenarios 1-6).

All tasks in this phase are **commit group A**, together with T024 and T025.

- [X] T010 [US1] In `server/features/members/dtos.py` replace `birth_date: date | None` with `birth_day: int | None`, `birth_month: int | None`, `birth_year: int | None` in `MemberRecordDTO`, `MemberCreateDTO` (each `= None`) and `MemberPatchDTO` (each `= None`); drop the `date` import only if nothing else uses it (`baptism_date` still does)
- [X] T011 [P] [US1] In `server/features/members/serializers/admin_member_serializers.py` replace `birth_date` in `MemberRecordSerializer` with three `serializers.IntegerField(allow_null=True)` and in `MemberPatchSerializer` with three `serializers.IntegerField(required=False, allow_null=True)` (no `min_value`/`max_value`: ranges are checked in the domain so messages carry the value, research R-03). The existing unknown-key check then rejects `birth_date`
- [X] T012 [P] [US1] In `server/features/members/repositories/member_roster_repository.py` replace `"birth_date"` in `_PATCH_COLUMNS` with `"birth_day"`, `"birth_month"`, `"birth_year"`, and in `_to_record` pass `birth_day=member.birth_day`, `birth_month=member.birth_month`, `birth_year=member.birth_year`
- [X] T013 [US1] In `server/features/members/services/member_roster_service.py` switch both call sites to `validate_member_date_parts`: `create_member` builds `BirthDateParts(dto.birth_day, dto.birth_month, dto.birth_year)`; `_check_patch` delegates to a new private `_merged_birth(dto, before) -> BirthDateParts` that takes each part from `dto` when its name is in `dto.model_fields_set` and from `before` otherwise (research R-04). Update imports
- [X] T014 [US1] In `server/features/members/domain/member_dates.py` delete the now-unused `validate_member_dates` (keep `_reject_future`, used by the new function) and in `server/features/members/tests/unit/test_member_dates.py` delete `class TestValidateMemberDates` (its cases are covered by `TestValidateMemberDateParts`, T003)
- [X] T015 [P] [US1] In `server/features/members/tests/fakes.py` replace `"birth_date": None` in `_blank_record` with `"birth_day": None, "birth_month": None, "birth_year": None`, and make `FakeMemberRosterRepository` store and return the three parts wherever it handled `birth_date`
- [X] T016 [P] [US1] In `server/features/members/tests/integration/test_member_roster_repository.py` replace the `birth_date=date(1990, 4, 2)` fixture and assertion with `birth_day=2, birth_month=4, birth_year=1990`, and add one case where `update` with `MemberPatchDTO(birth_year=None)` clears only the year
- [X] T017 [US1] In `server/features/members/tests/unit/test_member_roster_service.py` replace every `birth_date=` in DTOs, `h.roster.add(...)` calls and expected `MemberFieldChange`s with the three parts (expected history now has one entry per changed part, e.g. `MemberFieldChange(field="birth_year", old_value="1990", new_value="1991")`); rewrite `test_baptism_checked_against_stored_birth_date` to store `birth_year=2000` only and patch `baptism_date=date(1999, 5, 1)`
- [X] T018 [US1] In `server/features/members/tests/integration/test_admin_members_api.py` replace `"birth_date"` in the expected record keys with the three parts; replace every `birth_date=`/`"birth_date":` fixture and assertion with the parts; add tests for spec US1 scenarios 1-6 (four creates, one per valid state, reading back the parts; patch `{"birth_year": null}` keeps day and month; patch `{"birth_day": 5, "birth_month": 8}` on a year-only member returns the full date); add a test that `POST` with `{"name": "X", "birth_date": "1990-01-01"}` returns 400 `VALIDATION_ERROR` mentioning `birth_date` (contract, unknown key)

**Checkpoint**: Leader API speaks the new fields; MVP deliverable to the Android app.

---

## Phase 5: User Story 2 - Invalid birth information is rejected (Priority: P1)

**Goal**: Every invalid combination is refused through the API with a message naming the value,
and nothing (history included) is stored.

**Independent Test**: Send each invalid body to create and to patch; each returns 400 with the
value in `detail` and the record and history are unchanged.

- [X] T019 [P] [US2] In `server/features/members/tests/unit/test_member_roster_service.py` add: patch sending only `birth_day=31` on a stored member with `birth_month=4` is rejected naming `31/04` (merge with stored month, spec FR-006); patch sending `birth_month=None` on a member with a day is rejected naming `birth_day`; patch `birth_year=1990` on a stored 29/02 is rejected; a rejected patch writes no history (`FakeMemberChangeLogRepository` empty)
- [X] T020 [P] [US2] In `server/features/members/tests/integration/test_admin_members_api.py` add a parametrized test over the `contracts/admin-members-api.md` 400 examples (day without month, 31/04, 29/02/1990, year 2999 — not 2027, so the test does not depend on the real clock —, year 1990 with baptism 1989-05-01) plus day 0, month 13 and a string for `birth_day`: each returns 400 `VALIDATION_ERROR` whose `detail` contains the offending value, for both `POST` and `PATCH`; after a rejected `PATCH` the record and its history are unchanged. Freeze "today" the same way the existing future-date test in this file does

**Checkpoint**: All validation rules reachable end to end.

---

## Phase 6: User Story 3 - Birthdays list shows only real birthdays (Priority: P1)

**Goal**: The public birthdays endpoint reads the new columns; year-only and empty members are
absent; the response shape is unchanged.

**Independent Test**: Seed one member per valid state and call `GET api/members/birthdays/`
for their months.

- [X] T021 [US3] In `server/features/members/repositories/member_repository.py` rewrite `list_birthdays_by_month_range` to `Member.objects.filter(is_active=True, birth_day__isnull=False, birth_month__gte=start_month, birth_month__lte=end_month).order_by("birth_month", "birth_day").values_list("name", "gender", "birth_month", "birth_day")` and drop the `ExtractMonth`/`ExtractDay` import (research R-07)
- [X] T022 [P] [US3] In `server/features/members/management/commands/seed_birthdays.py` change `FAKE_MEMBERS` to `(name, gender, day, month, year)` tuples keeping the 30 existing dates, add three members — one day+month only (e.g. `("Helena Duarte", "F", 14, 8, None)`), one year only (`("Otavio Prado", "M", None, None, 1950)`), one with nothing (`("Sonia Reis", "F", None, None, None)`) — and pass `birth_day`/`birth_month`/`birth_year` in `defaults`; `--clear` keeps deleting by name. Covered by `server/features/members/tests/integration/test_seed_birthdays.py` (added: CLAUDE.md §10)
- [X] T023 [US3] In `server/features/members/tests/integration/test_birthdays_api.py` replace every `birth_date=date(Y, M, D)` with `birth_day=D, birth_month=M, birth_year=Y`; rename `test_excludes_null_birth_date` accordingly; add tests: a day+month-only member appears; a year-only member and an all-empty member do not; a 29/02 member appears in February with `birth_day == 29`; the response item keys are exactly `{"name", "gender", "birth_month", "birth_day"}`

**Checkpoint**: Birthdays built from the new columns, same shape as before.

---

## Phase 7: User Story 5 - Edit history tracks each part (Priority: P2)

**Goal**: History writes one row per changed part and keeps returning old `birth_date` rows.

**Independent Test**: Change only the year, then day and month together, and read the history;
insert an old-style `birth_date` row and read it back.

- [X] T024 [US5] In `server/features/members/domain/member_changes.py` replace `"birth_date"` in `HISTORY_FIELDS` with `"birth_day"`, `"birth_month"`, `"birth_year"` (in that order). **Commit group A**: `diff_member_records` reads these as `MemberRecordDTO` attributes, so this lands with T010
- [X] T025 [US5] In `server/features/members/tests/unit/test_member_changes.py` change `_record` defaults from `birth_date` to `birth_day=2, birth_month=4, birth_year=1990`; rewrite `test_one_change_per_differing_field` to change `birth_year` to 1991 and expect `MemberFieldChange(field="birth_year", old_value="1990", new_value="1991")`; add a test that changing day and month yields two entries in `HISTORY_FIELDS` order; add a test that clearing the year yields `new_value=None`. **Commit group A**
- [X] T026 [P] [US5] In `server/features/members/tests/integration/test_admin_member_history_api.py` add a test that a `MemberChangeLog` row created directly with `field="birth_date", old_value="1990-04-02", new_value="1991-01-01"` is returned unchanged by `GET api/admin/members/{id}/history/` (spec FR-013), and one that a `PATCH {"birth_year": 1991}` produces exactly one `birth_year` history row

**Checkpoint**: History correct for new edits and old rows.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Remove the old column, prove the conversion on production data, final checks.

- [X] T027 Remove `birth_date` from `Member` in `server/features/members/models/member.py`, run `python manage.py makemigrations members` to generate `server/features/members/migrations/0006_*.py` (unedited, `RemoveField`), then `makemigrations --check --dry-run`. Fix `test_birth_date_split_migration.py` if it relied on the latest state still having `birth_date` (it must use historical models only)
- [X] T028 Grep `server/` for `birth_date` (PowerShell `Select-String`, not Git Bash grep); the only hits allowed are migrations `0001_initial.py`, `0005_split_birth_date.py`, `0006_*.py`, and the history-row test from T026
- [X] T029 Run quickstart §1 from `server/`: `pytest features/members`, `pytest` (whole suite), `mypy .`, `ruff check .`, `black --check .`, `bandit -r features/members -q`; all green
- [ ] T030 Run quickstart §2 on a local PostgreSQL restored from a fresh production dump: save `_birth_before`, `migrate members 0005`, the zero-row comparison query, the year-0001 count check, then `migrate members` and drop `_birth_before`. Record the date of the check and the member count in the docstring of `server/features/members/migrations/0005_split_birth_date.py` (spec FR-016)
- [ ] T031 Run quickstart §3 (seed, leader PATCH/POST smoke tests, member birthdays call) against the local server
- [X] T032 [P] Confirm `specs/members/spec.md` matches the delivered code (fields, constraints, validation rule list, birthdays filter, history field names, admin limitation); fix any drift in the same commit as the code

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: none
- **Foundational (Phase 2)**: after Setup; blocks every story
- **US4 (Phase 3)**: after Phase 2 (needs 0004)
- **US1 (Phase 4)**: after Phase 2 (needs `validate_member_date_parts`, the columns)
- **US2 (Phase 5)**: after US1 (tests the service/API paths US1 switches)
- **US3 (Phase 6)**: after Phase 2 only; independent of US1/US2
- **US5 (Phase 7)**: T024/T025 are part of commit group A with US1; T026 after US1
- **Polish (Phase 8)**: after all stories; T027 before T028-T031; T030 before the deploy

### Commit groups

- **Group A** (one commit): T010-T018, T024, T025 — DTO change plus every reader of it
- Every other task or phase can be its own commit

### Within Each Story

- Domain rule before its caller; code and its updated tests in the same commit
- Spec already updated (`/speckit-specify`); T032 catches drift

### Parallel Opportunities

- Phase 2: T003 and T004 in parallel after T002; T007 after T006
- After Phase 2: US4 (T008-T009) and US3 (T021-T023) in parallel with US1
- In US1: T011, T012, T015, T016 touch different files
- US2: T019 and T020 in parallel

---

## Parallel Example: after Phase 2

```text
Developer A: T008 → T009            (US4 conversion)
Developer B: T021, T022 → T023      (US3 birthdays)
Developer C: T010 → T011, T012, T015, T016 → T013 → T014 → T017, T018, T024, T025  (group A)
```

---

## Implementation Strategy

### MVP First

1. Phases 1-2 (baseline, columns, rules)
2. Phase 3 (US4) — without conversion, the new columns are empty in production
3. Phase 4 (US1, commit group A) — leader API speaks the new fields
4. **Stop and validate**: quickstart §1, leader smoke tests

### Incremental Delivery

1. US2 tests harden validation end to end
2. US3 switches birthdays (must ship in the same deploy as US4, or the list goes empty)
3. US5 tests history
4. Phase 8 removes `birth_date` and runs the production-dump check; everything ships in one
   deploy (plan D-8)

---

## Notes

- `birth_date` stays on the model until T027 so every phase before it is type-correct alone.
- Error messages are Portuguese, carry the offending value and the expected shape (CLAUDE.md §8).
- Never edit 0004 or 0006 by hand; 0005 is the only hand-written migration.
- Commit spec and code together (CLAUDE.md §6.2).
