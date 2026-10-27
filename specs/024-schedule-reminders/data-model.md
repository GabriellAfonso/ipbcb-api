# Data Model: Rota Reminders by Push

## New: `schedule.ScheduleReminderClaim`

That one reminder kind was claimed for one member and one occasion (research R-01, R-02).

| Field      | Type                    | Constraints                                         |
|------------|-------------------------|-----------------------------------------------------|
| kind       | CharField(20)           | choices: `schedule_week`, `schedule_eve`, `schedule_published` |
| member     | FK(members.Member)      | CASCADE — a claim is bookkeeping, not history       |
| occasion   | CharField(32)           | `2026-10-26` (week), `2026-10-29/3` (eve), `2026-11` (publication) |
| run_id     | UUIDField               | the run that inserted the row (R-02)                |
| claimed_at | DateTimeField           | default=now                                         |

- **UniqueConstraint** `(kind, member, occasion)` named `unique_schedule_reminder_claim`.
- `Meta.ordering = ["-claimed_at"]`, `verbose_name = "schedule reminder claim"`.
- `__str__` → `"{kind} {occasion} member={member_id}"` (ids only, never the member name).
- Generated migration `schedule/0004`. Kept forever (a few hundred rows a month).

## Read: rota entries

`RotaEntryDTO` (Pydantic, `features/schedule/reminder_dtos.py`):

| Field            | Source                                              |
|------------------|-----------------------------------------------------|
| date             | `MonthlySchedule.date`                              |
| member_id        | `MonthlySchedule.member_id`                         |
| service_id       | `MonthlySchedule.schedule_type_id`                  |
| service_name     | `ChurchService.name`                                |
| start_time       | `ChurchService.start_time`                          |
| month_first_saved_at | earliest `created_at` of the same `(year, month)` (Subquery) |

## DTOs

- `RotaSlot(date, service, time)` — one slot on the wire; `time` as `HH:MM`.
- `ReminderKind` — `StrEnum` with the three wire values, also the claim `kind`.
- `ReminderClaimKey(member_id, occasion)` — frozen.
- `KindRunReport(kind, occasion_count, members, push: list[PushOutcome] summarised as devices/sent)`.
- `ScheduleReminderRunReport(reports: list[KindRunReport])`.

## Changed

- `core.application.dtos.push_dtos.PushMessage`: `slots: str | None`, `month: str | None`.
- `core.domain.push.PushMessageType`: `SCHEDULE_WEEK`, `SCHEDULE_EVE`, `SCHEDULE_PUBLISHED`.
- `features.schedule.services.schedule_service`: the 30-minute literal becomes
  `reminder_rules.OVERWRITE_WINDOW`.
