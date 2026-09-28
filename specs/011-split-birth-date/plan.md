# Implementation Plan: Split Member Birth Date into Day, Month and Year

**Branch**: `011-split-birth-date` | **Date**: 2026-09-28 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/011-split-birth-date/spec.md`

## Summary

Replace `Member.birth_date` with three nullable `PositiveSmallIntegerField`s (`birth_day`,
`birth_month`, `birth_year`) guarded by database check constraints for the day/month pair and
ranges. All cross-field rules (calendar date, 29/02, future, baptism before birth) live in the
pure `validate_member_date_parts` (replacing `validate_member_dates`), taking a `BirthDateParts` value and checked on the
merged record. Three migrations: generated add, hand-written irreversible data conversion (one
set-based `UPDATE`, year 1 becomes null), generated remove. Leader DTOs, serializers,
repository, history fields and the birthdays query switch to the new columns; the birthdays
response shape is unchanged.

## Technical Context

**Language/Version**: Python 3.14, `.venv_windows`

**Primary Dependencies**: Django 6, DRF, dependency-injector, Pydantic. No new dependency.

**Storage**: PostgreSQL in production, SQLite in tests. Three migrations (research R-02).

**Testing**: pytest + pytest-django; existing fakes (`FakeMemberRosterRepository`,
`FakeMemberChangeLogRepository`, `FixedClock`); migration test through
`django.db.migrations.executor.MigrationExecutor`; mypy, ruff, bandit.

**Target Platform**: Linux container behind nginx, prefix `/ipbcb/`.

**Project Type**: Web service (REST API), single Android client.

**Performance Goals**: Birthdays query stays one query, now without date extraction. Data
conversion is one `UPDATE` for the whole table.

**Constraints**: No compatibility for `birth_date` on leader routes (spec FR-008). Birthdays
response byte-identical in shape. Conversion irreversible (FR-015). Member data never in logs
(unchanged).

**Scale/Scope**: Hundreds of members; 1 model, ~10 source files, ~8 test files.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design — result unchanged.*

| Rule (`specs/constitution.md`, `CLAUDE.md`) | Status |
|---|---|
| Input validated by serializer before the DB; no raw `int()` | ✅ `IntegerField(allow_null=True)` for shape, domain rules in the service (R-03, R-05) |
| No queries in loops | ✅ conversion is one `UPDATE`; birthdays one query (R-02, R-07) |
| Layers: views → services → repositories; ORM only in repositories | ✅ unchanged; domain function stays pure |
| Domain exceptions, messages with value and shape | ✅ existing `ValidationError`, messages name the value (R-03) |
| DTOs are Pydantic; DI in `config/di.py` | ✅ DTO fields change; no new provider |
| Sensitive data: explicit serializer fields, member-free logs | ✅ fields listed explicitly; logs unchanged |
| Migrations generated, except data migrations with reason at top | ✅ 0004/0006 generated, 0005 data migration with reason (R-02) |
| Verification against a restored production dump | ✅ quickstart §2 (spec FR-016) |
| Models have `__str__`, `Meta.ordering`, `Meta.verbose_name` | ⚠️ `Member` gains `Meta` (constraints) but its pre-existing `ordering`/`verbose_name` gap (010 R-13) is not fixed here — adding `ordering` would change query order elsewhere |
| Spec and code in the same commit | ✅ domain spec already updated (`/speckit-specify`) |

Gate: **pass**.

## Technical Decisions

Full reasoning in [research.md](research.md).

- **D-1** Three `PositiveSmallIntegerField`s + three `CheckConstraint`s (pair, day range,
  month range), so the Django admin cannot store half a birthday (R-01).
- **D-2** Migrations 0004 (generated) → 0005 (data, one `UPDATE`, irreversible) → 0006
  (generated) (R-02).
- **D-3** `BirthDateParts` frozen dataclass + `validate_member_date_parts(birth, baptism, today)`, replacing `validate_member_dates` (new name so the old one can stay until the service switches, keeping each commit type-correct);
  29/02 via `calendar.monthrange(year or 2000, month)`; ranges checked in the domain for
  messages with the value (R-03).
- **D-4** Patch merges each part with the stored value before validating (R-04).
- **D-5** Serializers/DTOs: three nullable integers; `birth_date` rejected by the existing
  unknown-key check (R-05).
- **D-6** History: three tracked fields, `int` rendered as text; old `birth_date` rows
  untouched (R-06).
- **D-7** Birthdays filter/order on the columns directly (R-07).

- **D-8** Migration 0006 (removing `birth_date`) ships in the **same deploy** as 0004 and
  0005 (user decision, 2026-09-28). The conversion is verified on the restored dump beforehand
  (quickstart §2) and the pre-deploy dump is the recovery path (spec FR-015). Rejected: a
  second deploy keeping the unused column in production as a backup — one more release and a
  dead model field for a safety net the dump already gives.

## Implementation Order

Each step leaves the tree consistent for the mypy pre-commit hook (it checks the whole tree),
so model, DTOs and every consumer of `birth_date` change together.

1. **Domain rules**: `BirthDateParts` + new `validate_member_date_parts` in
   `domain/member_dates.py`; `int` branch in `render_history_value`. Unit tests: every row of
   `data-model.md`, Validation rules; int rendering.
2. **Model + migrations 0004/0005** (keep `birth_date` in the model until step 4): add fields
   and constraints, `makemigrations`; write `0005_split_birth_date.py` with the reason at the
   top. Tests: conversion cases, `IrreversibleError` on reverse, constraints refuse half pairs
   and out-of-range values.
3. **Switch every consumer** in one commit: DTOs, `_PATCH_COLUMNS` and `_to_record`,
   serializers, `MemberRosterService` (create + merged patch), `HISTORY_FIELDS`, birthdays
   repository, seed command, `tests/fakes.py`, and all tests that used `birth_date`
   (`test_admin_members_api`, `test_birthdays_api`, `test_member_roster_repository`,
   `test_member_roster_service`, `test_member_changes`, `test_member_dates`).
4. **Remove `birth_date`**: drop the model field, `makemigrations` → 0006. Grep for
   `birth_date` in `server/` returns only migrations 0001/0005.
5. **Validation**: quickstart §1, then §2 against the production dump, then §3.

## Project Structure

### Documentation (this feature)

```text
specs/011-split-birth-date/
├── spec.md
├── plan.md                         # this file
├── research.md                     # R-01 … R-10
├── data-model.md
├── quickstart.md
├── contracts/admin-members-api.md  # changed fields only
├── checklists/requirements.md
└── tasks.md                        # /speckit-tasks
```

### Source Code

```text
server/features/members/
├── domain/
│   ├── member_dates.py                    # BirthDateParts + rules
│   └── member_changes.py                  # HISTORY_FIELDS, int rendering
├── dtos.py                                # three int fields on record/create/patch
├── models/member.py                       # three fields + Meta.constraints, birth_date removed
├── migrations/
│   ├── 0004_<generated>.py                # add fields + constraints
│   ├── 0005_split_birth_date.py           # data migration, irreversible
│   └── 0006_<generated>.py                # remove birth_date
├── repositories/
│   ├── member_repository.py               # birthdays query
│   └── member_roster_repository.py        # _PATCH_COLUMNS, _to_record
├── serializers/admin_member_serializers.py
├── services/member_roster_service.py      # create + merged patch validation
├── management/commands/seed_birthdays.py
└── tests/
    ├── fakes.py
    ├── unit/test_member_dates.py
    ├── unit/test_member_changes.py
    ├── unit/test_member_roster_service.py
    ├── integration/test_birth_date_split_migration.py   # new
    ├── integration/test_member_constraints.py           # new
    ├── integration/test_birthdays_api.py
    ├── integration/test_admin_members_api.py
    └── integration/test_member_roster_repository.py
```

**Structure Decision**: Same layered layout; no new module besides the two test files. The
rule set stays in `domain/member_dates.py`, where the birth/baptism checks already live.

## Out of scope, found during planning (reported, not changed)

- `Member` still lacks `Meta.ordering`/`verbose_name` (010 R-13).
- Spec 010's `contracts/` and `data-model.md` still show `birth_date`; left as the record of
  that feature (R-10).
- Django admin still skips the calendar, future and baptism rules (only the constraints reach
  it); documented limitation from 010.

## Complexity Tracking

No constitution violations to justify.
