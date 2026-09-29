# Schedule Domain Spec

## Purpose

Builds and stores the monthly **rota** (escala): which member serves at which church service on
which date. An admin generates a preview, adjusts it, and saves it; members read the current month.

Selection is weighted and randomised, so the same admin generating twice gets different — but
equally valid — suggestions. Saving replaces the whole month.

> First written from the code on 2026-08-07 per CLAUDE.md §6.5, then updated when feature 007
> moved the service catalogue into `core/`.

---

## Data Models

### ChurchService — lives in `core/`, not here

The catalogue of recurring church services the rota is built from. Moved out of this
feature by 007 and now shared with `songs`, which needs the same services to group hymn
views. Formerly `schedule.ScheduleType`; the table and every id were preserved.

| Field      | Type                      | Constraints              |
|------------|---------------------------|--------------------------|
| name       | CharField                 | max=100                  |
| weekday    | PositiveSmallIntegerField | 1-7                      |
| start_time | TimeField                 |                          |
| end_time   | TimeField                 | strictly after start_time |
| active     | BooleanField              | default=True             |
| takes_rota | BooleanField              | default=True             |

**Weekday convention: `1 = Sunday … 7 = Saturday`** (Django's `__week_day`), *not* Python's
`datetime.weekday()`. Production holds Terça=3, Quinta=5, Domingo=1.

**`__str__`** → `"{name} - {id}"`

Production rows: `Terça de Oração` (3, 19:30), `Quinta de Oração` (5, 19:30),
`Domingo Liturgia de Adoração` (1, 19:30).

### MemberScheduleConfig

Which members may serve at which service, and how strongly to favour them.

| Field         | Type                | Constraints            |
|---------------|---------------------|------------------------|
| member        | FK(members.Member)  | CASCADE                |
| schedule_type | FK(core.ChurchService) | **PROTECT**         |
| available     | BooleanField        | default=True           |
| weight        | PositiveIntegerField| default=1              |

**unique_together**: `(member, schedule_type)`

The field is still named `schedule_type` although it points at `ChurchService`: it surfaces as `schedule_type_id` in the rota payloads the Android app sends and receives, so renaming it would change the wire format.

**`__str__`** → `"{member.name} - {schedule_type.name}"`

### MonthlySchedule

One saved rota assignment. This is the history the church cares about.

| Field         | Type                | Constraints                     |
|---------------|---------------------|---------------------------------|
| year          | PositiveIntegerField| not editable, derived from date |
| month         | PositiveSmallIntegerField | not editable, derived from date |
| date          | DateField           |                                 |
| schedule_type | FK(core.ChurchService) | **PROTECT**                  |
| member        | FK(members.Member)  | PROTECT                         |
| created_at    | DateTimeField       | default=now, not editable       |

**unique_together**: `(schedule_type, date)` — one member per service per date.

`save()` derives `year` and `month` from `date` on every write, so the two can never drift.

**`__str__`** → `"{member.name} - {dd/mm/yyyy} - {schedule_type.name}"`

> **Both foreign keys to the catalogue are `PROTECT`.** They were `CASCADE` until 2026-08-07:
> deleting a service silently erased every rota row that referenced it. Changed because feature 007
> makes service deletion reachable from an admin endpoint. Deactivate a service instead of deleting
> it.

---

## Endpoints

Prefixed with the base path (`/ipbcb/`).

### GET /api/schedule/current/

The current month's rota, grouped by service.

- **Auth**: `IsMemberUser`
- **Response**: `200` with ETag support (304 if unchanged)
- **Body**:
  ```json
  {
    "year": 2026,
    "month": 8,
    "schedule": {
      "Domingo Liturgia de Adoração": {
        "time": "19:30",
        "items": [
          {
            "date": "2026-08-02",
            "day": 2,
            "member": { "id": 7, "name": "..." },
            "schedule_type": { "id": 3, "name": "Domingo Liturgia de Adoração" }
          }
        ]
      }
    }
  }
  ```
- **Grouping key is the service *name***, so renaming a service changes the response shape.
- **Ordering**: service name, then date.

### POST /api/schedule/generate/

Generate a rota preview. **Writes nothing.**

- **Auth**: `IsAuthenticated` + `scope_permission(Scope.SCHEDULE)` — `manage` by method (POST), although it persists nothing (Admin, Liderança; `specs/012-feature-role-permissions/`)
- **Request**:
  ```json
  {
    "year": 2026,
    "month": 9,
    "fixed": [{ "schedule_type_id": 3, "date": "2026-09-06", "member_id": 10 }]
  }
  ```
- `year`/`month` omitted → **next month** relative to today.
- `fixed` pins a member to a `(service, date)` slot. Malformed entries are **skipped silently** —
  a bad `date` or a missing key drops that pin without an error.
- **Response**: `200` with `{ year, month, items: [...] }`, each item carrying `date`, `day`,
  `schedule_type` (`id`, `name`, `time`), `member` (`id`, `name`) and `fixed` (bool).
- **Ordering**: service name, then date.

### POST /api/schedule/save/

Persist a rota, replacing the whole month.

- **Auth**: `IsAuthenticated` + `scope_permission(Scope.SCHEDULE)` — `manage` (Admin, Liderança). Accepted risk: Liderança can overwrite a whole month; the guard against changing past months still applies
- **Request**: `{ year, month, items: [...] }`
- **Accepts two item shapes**, normalised by `_parse_schedule_save_payload`:
  - flat — `{"date": "...", "schedule_type_id": 3, "member_id": 10}`
  - nested — `{"date": "...", "schedule_type": {"id": 3}, "member": {"id": 10}}`, which is exactly
    what `/generate/` returns, so a preview can be posted back unmodified.
  - Items matching neither shape are **skipped silently**.
- **Response**: `200` with `{ "ok": true }`
- **Errors**:
  - `400` — `year` or `month` missing or not integers
  - `409` — the month was first saved more than 30 minutes ago (`ScheduleOverwriteError`)

---

## Business Rules

### Generation

1. **Every weekday generates.** The stored weekday is converted through
   `core/domain/weekday.py`. A service is skipped only when `takes_rota` is false — the one
   intentional exclusion, used by Escola Bíblica Dominical.
2. **Dates** are every occurrence of the service's weekday in the target month.
3. **Eligible members** are those with a `MemberScheduleConfig` for that service where `available`
   is true. A service with no configured members is skipped.
4. **Weighting** expands each member into `weight` copies of their id, then shuffles the list. A
   member with `weight=3` is three times as likely to be drawn.
5. **Spread across services**: `used_member_ids` accumulates across *all* services in the month, so
   a member already picked anywhere is deprioritised everywhere. If that leaves no candidates, the
   full weighted pool is reused.
6. **Least-used tie-break**: among candidates, anyone with zero assignments this month is preferred;
   otherwise the minimum usage count wins, with a random pick among ties.
7. **Pinned slots** bypass selection entirely, but still count toward usage — so pinning someone
   makes them less likely to be drawn elsewhere. A pin naming a member with no config for that
   service is ignored.
8. Generation is **not deterministic**. Two runs with the same input differ unless every slot is
   pinned.

### Saving

- **Replaces the whole month**: deletes every `MonthlySchedule` for that `(year, month)` and bulk
  creates the new set, inside one transaction.
- **30-minute overwrite window**: if the earliest `created_at` for the month is more than 30 minutes
  old, saving raises `ScheduleOverwriteError` → `409`. The intent is to allow correcting a rota just
  after publishing it, but not to let an old rota be silently rewritten later.
- The window is measured from the **earliest** row of the month, so repeated saves inside the window
  do not extend it.

### Metrics

`SCHEDULE_GENERATED_COUNTER` increments per preview, `SCHEDULE_SAVED_COUNTER` per save
(`core/metrics.py`).

---

## Architecture

Views → Services → Repositories → Models.

- **Repository**: `ScheduleRepositoryImpl` — the only ORM access. Uses `select_related` on member
  and service when listing.
- **Service**: `ScheduleService` — generation, grouping and the overwrite rule. Holds all business
  logic and imports no HTTP object.
- **DTOs**: `ScheduleTypeDTO`, `MemberConfigDTO`, `MonthlyScheduleDTO` (Pydantic).
- **DI**: registered in `config/di.py`, injected via `@inject` + `Provide[Container.schedule_service]`.
- **Errors**: `ScheduleOverwriteError` from `core/domain/exceptions.py`, mapped to `409` by the
  project's exception handler.

---

## Design Decisions

- **Weighted random rather than round-robin**: the church wants variety, not a fixed rotation.
  `random.choice` is adequate at 18 members.
- **Preview and save are separate calls**: an admin reviews and adjusts before anything is written.
- **Replace-the-month on save**: simpler than diffing, and matches how the rota is actually
  edited — regenerated wholesale, not row by row.
- **Tolerant payload parsing**: `/save/` accepts the exact output of `/generate/`, so the app can
  post a preview back without reshaping it.
- **Silent skipping of malformed `fixed` entries and items** is deliberate for pins (a stale pin
  should not block generating a month) but is *also* what hides the weekday bug below.

---

## Known Issues

- **`_parse_schedule_save_payload` skips unparseable items silently**, so a client bug can save a
  partial rota that looks successful.

---

## Related

- `specs/007-unify-service-catalogue/` — moves `ScheduleType` into a shared catalogue owned by
  `core/`, fixes both weekday issues, and adds the `takes_rota` distinction.
