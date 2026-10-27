# Feature Specification: Rota Reminders by Push

**Feature Branch**: `024-schedule-reminders`

**Created**: 2026-10-27

**Status**: Draft

**Input**: User description: "Remind every member who is on the monthly rota (escala) that they
serve, through push notifications to the Android app." (full request — current state, decisions
and their reasons — in `../TODO/specify_schedule_reminders_backend.md`; decided in session
`d5ff356e-47e7-428f-963b-df92f028c532`, 2026-10-27.)

## Context

The monthly rota (`specs/schedule/spec.md`) says which member leads each church service on each
date. Today it is only visible when someone opens the Escala screen, and people forget they lead
the Thursday prayer meeting. This feature makes the server tell each rota member, by push
notification, that they serve: once a week, the evening before each service, and when the month's
rota is published. The app (separate spec) only shows the notifications and owns the opt-out.

### Relation to other specs

- **`specs/schedule/spec.md`** — the domain spec; gains the reminders, their timing and their
  claims. The rota itself, its endpoints and the 30-minute overwrite window are unchanged.
- **`specs/017-sunday-setlist-push/`** — the push infrastructure (device tokens, data-only
  messages, invalid-token cleanup) and the pattern of a scheduled job that claims each occasion
  before sending. Reused as is.
- **`specs/022-access-requests/`** — the definition of member access (profile flag, or the Admin
  or Liderança role).
- **`specs/002-structured-json-logging/`**, **`specs/003-prometheus-grafana-metrics/`** — run
  outcomes are logged and pushes counted in their formats.

## Definitions

### Rota entry

One saved assignment of the rota: a date, a church service (name and start time) and the member
who serves.

### Rota recipient

A user whose profile is linked to the entry's member **and** who has member access. A member with
no linked profile, or whose linked account lacks member access or is inactive, receives nothing.

### Slot

What a reminder says about one rota entry: its date, the service name and the service start time
(`HH:MM`). No member name and no id of any person.

### Local time

All dates and hours are `America/Sao_Paulo`.

### Publication moment

The earliest save time of a month's rota plus 30 minutes — when the overwrite window closes and
the month can no longer change (`specs/schedule/spec.md`, Saving).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The evening before, the member is reminded they serve (Priority: P1)

The day before each rota entry, at 19:00, the member of that entry gets a push saying which
service they lead tomorrow and at what time. One push per entry.

**Why this priority**: this is the forgetfulness the feature exists to fix — about 24 hours before
the service is the reminder that changes whether the member shows up prepared.

**Independent Test**: with a fake clock and a fake push sender, save a rota with one Thursday
entry for a linked member, run the job on Wednesday at 18:59 and 19:05 and again at 19:30; expect
exactly one `schedule_eve` message to that member's user, sent at 19:05, carrying one slot.

**Acceptance Scenarios**:

1. **Given** a rota entry for Thursday whose member is linked to a user with member access, **When**
   the job runs on Wednesday at 19:05, **Then** that user receives one `schedule_eve` message whose
   single slot is Thursday's date, the service name and its start time.
2. **Given** the eve reminder for that entry was already sent, **When** the job runs again that
   evening — even after a restart, or two runs at once — **Then** nothing more is sent for it.
3. **Given** it is Wednesday before 19:00, **When** the job runs, **Then** no eve reminder for
   Thursday is sent.
4. **Given** the job was down all Wednesday evening, **When** it runs at 00:10 on Thursday, **Then**
   the eve reminder for Thursday is not sent — its service day has started.
5. **Given** a member serving two services on the same date, **When** the eve run happens, **Then**
   they receive two `schedule_eve` messages, one per entry.
6. **Given** the entry's member has no linked profile, or the linked account has no member access,
   **When** the job runs, **Then** nobody receives anything for that entry.

---

### User Story 2 - Monday morning, the member sees their week (Priority: P2)

Every Monday at 08:00, each member with at least one rota entry from that Monday to the following
Sunday gets one push listing their entries of the week in date order.

**Why this priority**: lets members plan the week; the eve reminder already covers the
forgetfulness, so this one adds value but is not the core.

**Independent Test**: with entries for one member on Tuesday and Sunday of the same week and none
for another member, run the job on Monday at 08:03; expect one `schedule_week` message to the first
member with both slots in date order, and nothing to the second.

**Acceptance Scenarios**:

1. **Given** a member with entries on Tuesday and Sunday of this week, **When** the job runs on
   Monday at 08:03, **Then** they receive one `schedule_week` message with both slots, Tuesday first.
2. **Given** a member with no entry from this Monday to Sunday, **When** the job runs, **Then** they
   receive nothing.
3. **Given** the week summary was already sent this Monday, **When** the job runs again on Monday,
   **Then** nothing more is sent.
4. **Given** the job was down from 07:00 to 15:00 on Monday, **When** it runs at 15:00, **Then** the
   summary is sent then; **Given** it was down all Monday, **When** it runs on Tuesday, **Then** the
   summary is not sent.
5. **Given** a week from 29 October to 4 November and November's rota not yet saved, **When** the
   summary is sent, **Then** it holds only the October entries; nothing else changes.
6. **Given** a member with a Tuesday entry, **When** Monday comes, **Then** they receive both the
   08:00 week summary and, at 19:00, the eve reminder for Tuesday.

---

### User Story 3 - The month's rota is published (Priority: P2)

When the rota for a month is saved and its 30-minute overwrite window closes, each member with at
least one entry dated today or later in that month gets one push listing those entries, with the
month, so they hear about it right away.

**Why this priority**: tells people the rota exists as soon as it is final; less urgent than the
eve reminder, which reaches them anyway before each service.

**Independent Test**: save a month at 10:00 with entries for two linked members; run the job at
10:20 and at 10:31; expect nothing at 10:20 and one `schedule_published` per member at 10:31, each
with the month and that member's entries.

**Acceptance Scenarios**:

1. **Given** a month first saved at 10:00, **When** the job runs at 10:20, **Then** nothing is
   published; **When** it runs at 10:31, **Then** each rota recipient receives one
   `schedule_published` message with `month` and their entries dated today or later, in date order.
2. **Given** the month was saved three times between 10:00 and 10:25, **When** the window closes,
   **Then** each member receives exactly one message, reflecting the last save.
3. **Given** the publication of a month was already sent, **When** the job runs again, **Then**
   nothing more is sent for that month.
4. **Given** a member whose only entries in the month are dated before today, **When** the month is
   published, **Then** they receive nothing.
5. **Given** a rota saved for next month, **When** its window closes, **Then** the publication is
   sent the same way, listing all of the member's entries in that month.
6. **Given** the job was down when the window closed and comes back the same day, **When** it runs,
   **Then** the publication is sent; **Given** it comes back on a later day, **Then** the publication
   is not sent.

---

### Edge Cases

- **A recipient has no registered device**: nothing reaches them; the occasion is still recorded as
  done, and the run continues with the others.
- **A recipient has several devices**: each device receives its own copy.
- **The push provider fails or credentials are missing**: logged as in feature 017; the occasion is
  still recorded as done, so a broken provider is not retried every minute.
- **A token the provider reports as gone**: deleted, as on every other push.
- **A member linked to an inactive account**: receives nothing.
- **A service later deactivated or renamed**: slots carry the service name current at send time.
- **Rotas older than this feature**: no publication is sent for a month whose publication moment
  is before today (FR-012 already covers this; nothing is backfilled).
- **Services without a rota (`takes_rota` false)**: they have no rota entries, so no reminder.
- **Removing a member from a rota**: only possible within the first 30 minutes, before anything has
  been sent, so nobody is ever told they serve and then silently removed.

## Requirements *(mandatory)*

### Functional Requirements

**Recipients and content**

- **FR-001**: Every reminder MUST be sent only to rota recipients (Definitions): users linked to the
  entry's member who have member access and an active account.
- **FR-002**: Each reminder MUST carry a list of slots, each with the entry's date (`YYYY-MM-DD`),
  the service name and the service start time (`HH:MM`), ordered by date and then start time. It
  MUST NOT carry any member name or any id of a person.
- **FR-003**: Each message MUST be built for one member and sent to that member's recipients only:
  no member receives another member's slots.
- **FR-020**: Each reminder MUST carry `gender` (`M` or `F`) when the member has one recorded,
  and leave the key out otherwise, so the app can word it "escalado"/"escalada", "o
  responsável"/"a responsável". It is the recipient's own data, sent only to their own devices.
- **FR-019**: Every reminder MUST consider only entries of months whose publication moment has
  passed. A month still inside its 30-minute overwrite window can be replaced wholesale, so
  reminding from it could tell someone they serve and then silently remove them — the same reason
  the publication waits for the window (FR-010).

**Week summary (`schedule_week`)**

- **FR-004**: On Monday from 08:00 until midnight, the job MUST send each member with at least one
  entry dated from that Monday to the following Sunday, inclusive, one `schedule_week` message with
  all of those entries.
- **FR-005**: Entries of a following month that is not saved yet are simply absent; no special
  handling.

**Eve reminder (`schedule_eve`)**

- **FR-006**: For each rota entry, from 19:00 until midnight of the day before its date, the job
  MUST send the entry's member one `schedule_eve` message carrying exactly that entry's slot.
- **FR-007**: The eve reminder of an entry MUST NOT be sent once the entry's date has started.
- **FR-008**: A Monday eve reminder (for a Tuesday entry) and the Monday week summary are both sent;
  the overlap is accepted.

**Publication (`schedule_published`)**

- **FR-009**: Once a month's publication moment has passed, the job MUST send each member with at
  least one entry in that month dated today or later one `schedule_published` message with the
  month (`YYYY-MM`) and those entries.
- **FR-010**: The publication MUST be sent at most once per month, reflecting the rota as it stands
  after the overwrite window closed — never on each save.
- **FR-011**: The publication MUST be sent within a few minutes of the publication moment while
  the job is running.
- **FR-012**: A publication whose moment fell on an earlier day than today MUST NOT be sent.

**Sending once**

- **FR-013**: Each reminder MUST go out at most once per member and occasion — the Monday's date for
  the week summary, the rota entry for the eve reminder, the month for the publication — across
  restarts and overlapping runs. The occasion is recorded as done before the push is sent.
- **FR-014**: An occasion missed while the job was not running MUST still be sent later on the same
  day (inside its window), and MUST NOT be sent on a later day.
- **FR-015**: A push failure MUST NOT stop the run nor un-record the occasion; it is logged.

**Running**

- **FR-016**: The reminders MUST run from a management command invoked in a loop about every minute
  by a container in `compose.prod.yml`, like `send_setlist_reminders`. No task queue.
- **FR-017**: Each run MUST log its outcome per reminder kind with counts and dates only, and the
  pushes MUST be counted by type in the existing push metric.

**Out of scope**

- **FR-018**: No preference endpoint and no stored opt-out on the server: the opt-out is in the app,
  which drops the message on the device.

### Payload

Data-only messages, every value a string (see `contracts/push-messages.md`):

```json
{ "type": "schedule_week", "slots": "[{\"date\":\"2026-10-27\",\"service\":\"Terça de Oração\",\"time\":\"19:30\"}]" }
{ "type": "schedule_eve", "slots": "[{\"date\":\"2026-10-29\",\"service\":\"Quinta de Oração\",\"time\":\"19:30\"}]", "gender": "F" }
{ "type": "schedule_published", "month": "2026-11", "slots": "[...]" }
```

`gender` (`M`/`F`) is present only when the member has one recorded (FR-020). `slots` is a JSON-encoded array. Service names are carried, unlike earlier push types that carry
only a date, because the app must show the notification at once, even offline, and the service name
and time are church catalogue data, not member or user data.

### Key Entities

- **Rota entry** (existing `MonthlySchedule`): read only — date, service, member, save time.
- **Church service** (existing `core.ChurchService`): name and start time feed the slots.
- **Reminder claim**: the record that one reminder kind was sent to one member for one occasion —
  kind, member, occasion, when claimed. Unique per (kind, member, occasion). How it is stored is a
  plan decision.
- **Profile ↔ member link** and **member access** (existing, `accounts`): decide recipients.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Every rota recipient with a registered device receives the eve reminder before each of
  their services, within 5 minutes after 19:00 the day before, while the job runs.
- **SC-002**: No member ever receives the same reminder twice for the same occasion, including
  across job restarts.
- **SC-003**: A rota saved several times inside its 30-minute window produces exactly one
  publication message per member, sent within 2 minutes after the window closes.
- **SC-004**: No message ever contains another member's slots or any member name.
- **SC-005**: Within two months of release, the leader reports fewer services where the scheduled
  member forgot (qualitative feedback).

## Assumptions

- The two hours (Monday 08:00, eve 19:00) were chosen from "segunda de manhã" and "véspera" in the
  decision conversation.
- The deacon saves the rota on the first day of the month; a month saved in advance is rare, so the
  week summary crossing into an unsaved month needs no handling.
- Recipients are resolved at send time: a profile linked or member access granted after the rota
  was saved still receives later reminders.
- The reminder job shares the existing `./.env` and push credentials with the setlist reminder.
- Claims are kept; their volume (a few hundred rows a month) needs no purge for now.
