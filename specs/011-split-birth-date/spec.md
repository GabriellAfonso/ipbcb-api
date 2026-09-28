# Feature Specification: Split Member Birth Date into Day, Month and Year

**Feature Branch**: `011-split-birth-date`

**Created**: 2026-09-28

**Status**: Draft

**Input**: User description: "Split member birth date into three independent optional fields.
Member.birth_date cannot represent partial dates: the secretary stores 'birthday known, year
unknown' as year 0001 (undocumented convention), and 'year known, day/month unknown' cannot be
stored at all." (full request, including validation, migration, API and history rules, in the
`/speckit-specify` invocation that created this directory)

## Overview

A member's birth date is stored today as one full calendar date. The church often knows only
part of it:

- **Birthday known, year unknown** — common for older members. The secretary types year 0001
  as a placeholder. Nothing documents this, and the leader screen (spec 010) shows it as a real
  date.
- **Year known, birthday unknown** — cannot be stored at all. Any placeholder day and month
  becomes a fake birthday in the members' birthdays list.

This feature replaces the single date with three independent optional parts — day, month and
year — so the roll records exactly what is known and nothing more. Existing records are
converted automatically, turning the year-0001 placeholder into "year unknown".

**Domain spec**: `specs/members/spec.md` describes the members domain with the new fields.

**Scope**: backend only. The Android leader screen (not yet in production) adapts in the app
repository.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Leader records a partially known birth date (Priority: P1)

A leader edits or creates a member and fills in only what the church knows: the full date,
only the birthday (day and month), only the year, or nothing. The record shows back exactly
those parts.

**Why this priority**: This is the problem the feature exists to solve; without it the roll
keeps holding placeholders that read as facts.

**Independent Test**: Through the leader endpoints, create one member for each of the four
combinations and read each record back.

**Acceptance Scenarios**:

1. **Given** a leader creating a member, **When** they send day 12, month 3 and year 1990,
   **Then** the record returns day 12, month 3, year 1990.
2. **Given** a leader creating a member, **When** they send day 12 and month 3 with no year,
   **Then** the record returns day 12, month 3 and an empty year.
3. **Given** a leader creating a member, **When** they send only year 1950, **Then** the record
   returns empty day, empty month, year 1950.
4. **Given** a leader creating a member, **When** they send no birth fields, **Then** all three
   are empty.
5. **Given** a member with day 12, month 3, year 1990, **When** a leader clears only the year,
   **Then** the record keeps day 12 and month 3 with an empty year.
6. **Given** a member with only year 1950, **When** a leader adds day 5 and month 8,
   **Then** the record returns the full date 5/8/1950.

---

### User Story 2 - Invalid birth information is rejected (Priority: P1)

A leader who sends an impossible or inconsistent birth date is told exactly what is wrong,
and nothing is stored.

**Why this priority**: Splitting the date removes the calendar's built-in checks; without
explicit rules the roll could hold "31/02" or a birthday with no month.

**Independent Test**: Send each invalid combination below to create and to edit; each is
rejected with a message naming the offending value and the expected shape, and the stored
record is unchanged.

**Acceptance Scenarios**:

1. **Given** a create or edit, **When** the result would have a day without a month (or a
   month without a day), **Then** it is rejected.
2. **Given** a create or edit, **When** day and month do not form a real calendar date (e.g.
   31/04, 30/02, day 0, month 13), **Then** it is rejected.
3. **Given** a create or edit with day 29, month 2, **When** the year is empty or a leap year
   (e.g. 2000), **Then** it is accepted; **When** the year is not a leap year (e.g. 1990),
   **Then** it is rejected.
4. **Given** today is 2026-09-28, **When** the year is 2027, **Then** it is rejected; **When**
   the full date is 2026-10-01, **Then** it is rejected; **When** only day 1 and month 10 are
   given, **Then** it is accepted (a birthday alone is never "in the future").
5. **Given** a full birth date of 1990-03-12, **When** the baptism date is 1990-03-11,
   **Then** it is rejected.
6. **Given** only birth year 1990, **When** the baptism date is in 1989, **Then** it is
   rejected; **When** it is in 1990, **Then** it is accepted.
7. **Given** only birth day and month, **When** any baptism date is sent, **Then** no
   baptism-versus-birth check applies.
8. **Given** a stored member with day 12 and month 3, **When** an edit sends only a new day,
   **Then** the rules are checked against the record as it would be after the edit (day from
   the edit, month from the stored record).

---

### User Story 3 - Birthdays list shows only real birthdays (Priority: P1)

Members see the birthdays of the month. Members whose day and month are known appear; members
with only a year, or with no birth information, do not.

**Why this priority**: The birthdays list is the one regular-member feature built on this
data, and it is the place where placeholder dates did visible harm.

**Independent Test**: Seed members with each combination and request the birthdays for their
months.

**Acceptance Scenarios**:

1. **Given** valid profiles with full date, day+month only, year only and nothing, **When**
   the birthdays for the relevant months are requested, **Then** only the first two appear.
2. **Given** several birthdays in a month range, **When** the list is requested, **Then** they
   are ordered by month, then day.
3. **Given** any request, **When** the response is returned, **Then** its shape is unchanged:
   name, gender, month and day per entry.
4. **Given** a member born 29/02, **When** the February birthdays are requested in a non-leap
   year, **Then** the member appears on day 29 as-is.

---

### User Story 4 - Existing records are converted without data entry (Priority: P1)

When the change is deployed, every existing record is converted automatically. Nobody re-types
anything, and the year-0001 placeholder stops being a year.

**Why this priority**: The roll already holds real data; a conversion that loses or
misreads it would undo the feature's purpose.

**Independent Test**: Restore a production dump, run the conversion, and compare every member
before and after.

**Acceptance Scenarios**:

1. **Given** a member with birth date 1990-03-12, **When** the conversion runs, **Then** it has
   day 12, month 3, year 1990.
2. **Given** a member with birth date 0001-07-25, **When** the conversion runs, **Then** it has
   day 25, month 7 and an empty year.
3. **Given** a member with no birth date, **When** the conversion runs, **Then** all three
   parts are empty.
4. **Given** the conversion was applied, **When** someone tries to undo it, **Then** it refuses
   with an explicit error; recovery is restoring the dump taken before the deploy.
5. **Given** the conversion ran, **When** it is verified against the restored production dump,
   **Then** the old single-date field is removed only in a later, separate step.

---

### User Story 5 - Edit history tracks each part (Priority: P2)

A leader reading a member's history sees changes to day, month and year as separate entries,
and older entries about the single birth date keep reading as they did.

**Why this priority**: History keeps working with the new fields; it is not the feature's
goal, so it follows P1.

**Independent Test**: Edit only the year of a member, then edit day and month together, and
read the history.

**Acceptance Scenarios**:

1. **Given** a member with day 12, month 3, year 1990, **When** a leader changes only the year
   to 1991, **Then** one history entry is written for the year, old "1990", new "1991".
2. **Given** the same member, **When** a leader changes day and month in one edit, **Then** two
   entries are written, one per part.
3. **Given** history entries recorded before this change with field "birth_date", **When** the
   history is read, **Then** they appear unchanged.

---

### Edge Cases

- **Existing rows with a date before the year-0001 convention** (e.g. 1900-01-01 used as a
  placeholder): converted as real dates; only year 1 is treated as "unknown".
- **Existing rows that break the new rules** (future dates, baptism before birth): converted
  as they are; the rules apply only to writes, as in spec 010.
- **Edit that clears the month while keeping the day**: rejected (day without month); the leader
  must clear both.
- **Very old or implausible year** (e.g. year 5): accepted. The year has no lower bound; any
  positive year up to the current one is valid. The year-1 rule applies only to the conversion
  of existing rows, not to new writes.
- **Non-integer or negative values** for day, month or year: rejected as validation errors,
  never a server error.

## Requirements *(mandatory)*

### Functional Requirements

**Data**

- **FR-001**: A member's birth information MUST be three independent optional parts: day,
  month and year. The single birth date is removed.
- **FR-002**: Day and month MUST be both filled or both empty. Year is independent. The only
  valid combinations are: full date, day and month only, year only, nothing.

**Validation** (every rejection names the offending value and the expected shape)

- **FR-003**: Day and month MUST form a real calendar date. 29/02 is valid when the year is
  empty or a leap year, and invalid with a non-leap year.
- **FR-004**: The year MUST be a positive number and MUST NOT be after the current year; there
  is no lower bound. A full date MUST NOT be after today.
  Day and month alone are never checked against today.
- **FR-005**: The baptism date MUST NOT be before birth, compared only on what is known: full
  birth date against the baptism date; birth year alone against the baptism year; no check
  when only day and month are known.
- **FR-006**: Every rule MUST be checked against the record as it would be after the write, so
  an edit sending only some parts is checked with the stored values of the others.
- **FR-007**: A rejected write MUST store nothing, history included.

**Leader API** (spec 010)

- **FR-008**: The member record, the create body and the edit body MUST carry `birth_day`,
  `birth_month` and `birth_year` in place of `birth_date`. Each can be sent as empty to clear
  it. No compatibility period: `birth_date` is no longer accepted or returned.
- **FR-009**: The leader list MUST NOT gain birth fields (it does not carry a birth date today).

**Birthdays**

- **FR-010**: The birthdays list MUST keep its response shape (name, gender, month, day) and
  its access rules, and MUST be built from the new day and month.
- **FR-011**: Only valid profiles with both day and month appear; ordered by month, then day.
  29/02 is shown as day 29 in every year.

**History**

- **FR-012**: Day, month and year MUST each be a separate history field (`birth_day`,
  `birth_month`, `birth_year`), written only when that part changed. Values are stored as
  plain numbers in text; an empty part as none.
- **FR-013**: History entries with field `birth_date` already stored MUST stay unchanged and
  keep being returned.

**Conversion**

- **FR-014**: Existing records MUST be converted automatically: day and month copied from the
  single date; year copied unless it is 1, in which case the year is empty. Members without a
  date get three empty parts.
- **FR-015**: The conversion is one-way. Undoing it MUST fail with an explicit error, never
  silently leave members without birth data. Recovery is restoring the production dump taken
  before the deploy.
- **FR-016**: The conversion MUST be verified against a restored production dump before the
  single-date field is removed. The removal is a separate, later step.
- **FR-017**: The reason for the conversion (the year-0001 convention and the lost-year problem)
  MUST be documented at the top of the conversion step.

**Tooling and tests**

- **FR-018**: The local seed command for birthdays MUST create members through the new parts,
  including at least one of each combination (full date, day+month only, year only, nothing).
- **FR-019**: Every existing test that uses the single birth date MUST be updated to the new
  parts; each rule in FR-002 to FR-006 and each conversion case in FR-014/FR-015 MUST have a
  test.

### Key Entities

- **Member**: a person on the church roll. Birth information is now three optional parts —
  day, month, year — instead of one date. Every other attribute is unchanged.
- **Member change log entry**: unchanged shape; the tracked field names now include
  `birth_day`, `birth_month`, `birth_year`. Old `birth_date` entries remain.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A leader can record each of the four combinations (full, birthday only, year
  only, nothing) for any member, and reads back exactly what was entered.
- **SC-002**: After conversion of the production data, 100% of members keep the same day and
  month they had, 100% of real years are kept, and 0 members carry year 0001.
- **SC-003**: 0 members with only a year, or with no birth information, appear in the
  birthdays list.
- **SC-004**: For the same data (with year 0001 counted as unknown), the birthdays list
  returns the same entries, in the same order and shape, as before the change.
- **SC-005**: 100% of invalid combinations in User Story 2 are rejected with a message naming
  the value and the expected shape, and leave the record unchanged.

## Assumptions

- **Decided here:** no reverse conversion. The request asked for one, but it adds nothing once
  the single-date field is removed, and a production dump taken before the deploy is the
  recovery path. CLAUDE.md §5 requires a tested rollback only for model moves and field
  renames, not for this data conversion.
- A production dump is taken right before the deploy.
- The Android app does not use the leader endpoints in production yet, so the field change
  needs no compatibility period (as stated in the request).
- Year 1 is never a real birth year in this roll; every year-1 value is the placeholder.
- Day and month are validated as whole numbers: day 1-31, month 1-12, then as a calendar date.
- "Today" and "current year" come from the server clock already used by spec 010's date rules.
- The Django admin keeps editing `Member` directly (spec 010, known limitation). Database
  constraints stop it from storing a day without a month or out-of-range values; the calendar,
  future and baptism rules apply only through the leader endpoints (plan D-1).
- Out of scope: age calculation, any change to the baptism date, special handling of 29/02 in
  non-leap years in the birthdays list.

## Dependencies

- Spec 010 (members management) is implemented; this feature changes its birth date field.
- A production database dump is available for the conversion check (FR-016).
