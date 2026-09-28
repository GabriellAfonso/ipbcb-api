# Data Model: Split Member Birth Date

Only what changes. Everything else is as in `specs/010-members-management/data-model.md` and
`specs/members/spec.md`.

## Member (`features/members/models/member.py`)

| Field | Before | After |
|---|---|---|
| `birth_date` | `DateField(null=True, blank=True)` | removed (migration 0006) |
| `birth_day` | — | `PositiveSmallIntegerField(null=True, blank=True)` |
| `birth_month` | — | `PositiveSmallIntegerField(null=True, blank=True)` |
| `birth_year` | — | `PositiveSmallIntegerField(null=True, blank=True)` |

`Meta.constraints` (research R-01):

| Name | Condition |
|---|---|
| `member_birth_day_month_together` | `(birth_day IS NULL) = (birth_month IS NULL)` |
| `member_birth_day_range` | `birth_day IS NULL OR 1 <= birth_day <= 31` |
| `member_birth_month_range` | `birth_month IS NULL OR 1 <= birth_month <= 12` |

A model comment states why the date is split (partial dates, no placeholder year).

### Valid states

| day | month | year | Meaning | In birthdays |
|---|---|---|---|---|
| set | set | set | full date | yes |
| set | set | null | birthday known, year unknown | yes |
| null | null | set | year known only | no |
| null | null | null | nothing known | no |
| set | null | any | **invalid** (constraint + service) | — |
| null | set | any | **invalid** (constraint + service) | — |

## Validation rules (service, `domain/member_dates.py`)

Checked on the record as it would be after the write (research R-03, R-04). Every message
carries the offending value and the expected shape.

| Rule | Rejected example | Accepted example |
|---|---|---|
| day 1-31, month 1-12, year 1-9999 | day 0, month 13, year 0 | day 31, month 12, year 1 |
| day and month together | day 12, month null | day 12, month 3 |
| real calendar date | 31/04; 30/02; 29/02/1990 | 29/02 no year; 29/02/2000 |
| year not after current year | 2027 (today 2026-09-28) | 2026 |
| full date not after today | 2026-10-01 | 2026-09-28 |
| day+month alone never future | — | 01/10 no year |
| baptism not in the future | unchanged from 010 | — |
| baptism vs full birth date | birth 1990-03-12, baptism 1990-03-11 | same day |
| baptism vs birth year only | birth 1990, baptism 1989-12-31 | baptism 1990-01-01 |
| baptism vs day+month only | — (no check) | any baptism |

## Domain value

```text
BirthDateParts (frozen dataclass, domain/member_dates.py)
  day: int | None
  month: int | None
  year: int | None
```

Pure value passed to `validate_member_date_parts(birth, baptism_date, today)`. Not a DTO: it never
crosses a layer boundary.

## DTOs (`features/members/dtos.py`)

| DTO | Change |
|---|---|
| `MemberRecordDTO` | `birth_date: date \| None` → `birth_day`, `birth_month`, `birth_year: int \| None` |
| `MemberCreateDTO` | same, each defaulting to `None` |
| `MemberPatchDTO` | same, each defaulting to `None`; `model_fields_set` tells "not sent" from "cleared" |
| `BirthdayDTO` | unchanged (`birth_month: int`, `birth_day: int`) |

## MemberChangeLog

Shape unchanged. `field` may now be `birth_day`, `birth_month` or `birth_year`; values are the
number as text (`"12"`) or null. Rows with `field = "birth_date"` written before this feature
stay as they are.

## Migrations (`features/members/migrations/`)

| File | Kind | Content |
|---|---|---|
| `0004_…` | generated | add three columns + three constraints |
| `0005_split_birth_date.py` | hand-written data migration | reason at top; one `UPDATE` (research R-02); no reverse (irreversible) |
| `0006_…` | generated | remove `birth_date` |

Conversion table (0005):

| `birth_date` | `birth_day` | `birth_month` | `birth_year` |
|---|---|---|---|
| `1990-03-12` | 12 | 3 | 1990 |
| `0001-07-25` | 25 | 7 | null |
| null | null | null | null |
