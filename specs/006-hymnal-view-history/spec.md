# Feature Specification: Hymnal View History

**Feature Branch**: `006-hymnal-view-history`

**Created**: 2026-08-07

**Status**: Draft

**Input**: User description: "Add hymnal view history tracking to the backend, so the church can see which hymns the congregation actually opens and sings — during the week and on Sundays."

> **Access terms superseded by `specs/012-feature-role-permissions/`.** Below, "admin", "leader"
> and "church leaders" meant `Profile.is_admin` / `IsAdminUser`. Both are gone: access is now a
> role (Admin, Liderança, Mídia) with a level on a scope. The tables that named the old flag are
> updated; the narrative is kept as the record of this feature.

## Overview

Today the church only knows which songs were *planned* for a Sunday: an admin manually registers the
official repertoire (`Played` → `Song`). Nobody knows which **hymns** the congregation actually
opened and sang, either on Sunday or during the week.

This feature adds **passive usage history for the hymnal**. The Android app records when a hymn is
opened and for how long, buffers those records offline, and syncs them to the backend. Leadership
can then see which hymns were sung in a period and which are the most sung of all time.

This is a **separate concern** from the existing Sunday repertoire:

| | Existing `Played` / `RegisterSundayPlaysAPI` | New hymnal view history |
|---|---|---|
| Points to | `Song` | `Hymn` |
| Origin | Manually registered by an admin | Passively collected by the app |
| Meaning | Official planned repertoire | What the congregation actually opened |

Both must coexist. Nothing in the existing play-registration flow changes.

**Scope**: backend only. The Android app implementation is out of scope for this spec; the app is
described here only as the consumer whose behaviour the contract must support.

**Placement**: this lives inside the existing `songs` feature, because `Hymn` lives there and the
constitution forbids features importing from each other. No new Django app, no import from the
`schedule` feature.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The app syncs what the congregation viewed (Priority: P1)

A member opens hymn 50 during the Sunday evening service and keeps it on screen while the
congregation sings it. The app counts that as a view and stores it locally. Later — possibly hours
later, when the phone has network again — the app sends the buffered views to the backend in one
batch and deletes its local copy of everything the backend confirmed.

**Why this priority**: without ingest there is no data at all. Every other story reads what this
one writes. This is the MVP.

**Independent Test**: send a batch of view records and confirm each one is either stored or
explicitly answered for, then confirm a re-send of the same batch creates nothing new and still
answers positively.

**Acceptance Scenarios**:

1. **Given** a batch of valid view records for existing hymns, **When** the app sends it, **Then**
   the backend stores each record and returns every identifier in `accepted`.
2. **Given** a batch where one record references a hymn number that does not exist, **When** the
   app sends it, **Then** the other records are still stored and only the bad one comes back in
   `rejected` with a reason.
3. **Given** a batch that was already sent successfully but whose response the app never received,
   **When** the app re-sends the identical batch, **Then** no duplicate records are created and
   every identifier still comes back in `accepted`.
4. **Given** a member who opened hymn 50 for 30s, left, and came back and opened it again 4 minutes
   later on the same device, **When** both records are sent, **Then** only one record is kept and
   both identifiers come back in `accepted`.
5. **Given** a request from a device with no logged-in user, **When** it sends view records,
   **Then** the records are stored with no user attached and are still counted in history.
6. **Given** a request carrying a valid credential, **When** it sends view records, **Then** the
   records are attributed to that user.

---

### User Story 2 - Leadership sees which hymns were sung in a period (Priority: P2)

A church leader opens the admin area of the app and asks "which hymns were sung this month?" They
get one entry per hymn per moment it was sung — not one entry per person who happened to open it.
Two members opening hymn 50 at 19:30 on the same Sunday is **one** occurrence of hymn 50, not two.

**Why this priority**: this is the reason the data is collected. It turns raw view records into an
answer the church can act on.

**Independent Test**: seed view records from several devices inside and outside service times, then
request a date range and confirm the collapsing produces the expected number of occurrences.

**Acceptance Scenarios**:

1. **Given** three devices that viewed hymn 50 during the Sunday evening service window, **When**
   a leader asks for that week, **Then** the result shows one occurrence of hymn 50 for that
   service, reporting 3 contributing devices.
2. **Given** hymn 50 viewed during the Sunday morning service and again during the Sunday evening
   service, **When** a leader asks for that week, **Then** the result shows two separate
   occurrences.
3. **Given** hymn 120 viewed twice on a Wednesday afternoon, outside every configured service
   window, **When** a leader asks for that week, **Then** the result shows one occurrence for that
   calendar day.
4. **Given** a requested range and a grouping choice of day, week or month, **When** a leader asks,
   **Then** each occurrence reports which bucket it belongs to.
5. **Given** a non-admin user, **When** they request this data, **Then** access is denied.

---

### User Story 3 - Leadership sees the all-time hymn ranking (Priority: P3)

A leader wants a chart: hymn number on one axis, how many times it was sung on the other. They can
optionally narrow it to a period; by default it covers all recorded history.

**Why this priority**: valuable, but it is a second reading of the same collapsed data that Story 2
already defines. It adds insight, not new capability.

**Independent Test**: seed a known set of occurrences and confirm the ranking counts and ordering
match, and that hymns with no occurrences are absent.

**Acceptance Scenarios**:

1. **Given** recorded history, **When** a leader requests the ranking with no period, **Then** all
   hymns that have at least one occurrence are returned, ordered from most to least sung.
2. **Given** a hymn that was never viewed, **When** a leader requests the ranking, **Then** that
   hymn does not appear in the result.
3. **Given** five devices that contributed to a single occurrence, **When** a leader requests the
   ranking, **Then** that hymn is counted once, not five times.
4. **Given** a period is supplied, **When** a leader requests the ranking, **Then** only
   occurrences inside that period are counted.

---

### User Story 4 - An admin tunes collection behaviour without a deploy (Priority: P4)

The 30-second threshold that decides "this was a real view, not a mis-tap" turns out to be wrong for
this church. An admin changes it from the app and every device picks up the new value on its next
startup — no release, no deploy.

**Why this priority**: the system works with the built-in defaults; this only removes the need for a
deploy to change them.

**Independent Test**: read the settings without credentials, update one value as an admin, read it
again and confirm the new value, and confirm already-stored history is untouched.

**Acceptance Scenarios**:

1. **Given** a fresh install with no logged-in user, **When** the app reads the settings on
   startup, **Then** it receives the current values without needing credentials.
2. **Given** an admin, **When** they change the minimum view duration, **Then** subsequent reads
   return the new value.
3. **Given** existing stored history, **When** an admin changes any setting, **Then** no stored
   record is altered, removed or re-evaluated.
4. **Given** a non-admin, **When** they try to change a setting, **Then** the change is denied.
5. **Given** an invalid value (zero, negative, or beyond the allowed maximum), **When** an admin
   submits it, **Then** the change is rejected with a message naming the field, the offending value
   and the accepted range.

---

### User Story 5 - An admin maintains the church service windows (Priority: P5)

The church changes the Sunday evening service from 19:00 to 18:30, or adds a midweek prayer
meeting. An admin edits the service windows from the app so that future dashboards group views
correctly.

**Why this priority**: the seeded windows already cover the current schedule, and views outside every
window still collapse by calendar day. This is maintenance, not a blocker.

**Independent Test**: create, list, update and delete a window as an admin, and confirm the
validation rejects an end time that is not after the start time and a weekday outside 0–6.

**Acceptance Scenarios**:

1. **Given** an admin, **When** they create a window with a valid weekday and time range, **Then**
   it is stored and appears in the list.
2. **Given** an admin, **When** they submit an end time earlier than or equal to the start time,
   **Then** it is rejected with a message naming both values.
3. **Given** an admin, **When** they submit a weekday outside 0–6, **Then** it is rejected with a
   message naming the offending value and the accepted range.
4. **Given** a window is deactivated or deleted, **When** a leader asks for a period, **Then**
   occurrences are recomputed from the currently configured windows — stored view records are never
   modified.

---

### Edge Cases

- **Batch too large** — a batch above the configured maximum is rejected as a whole, so the app
  learns to split rather than silently losing records.
- **Empty batch** — an empty list is a valid no-op and returns empty `accepted` and `rejected`.
- **Clock skew forward** — a device whose clock is ahead sends a view time in the future; anything
  beyond the configured tolerance is rejected with a reason, never stored.
- **Very old records** — a device that was offline for months sends records older than the
  configured retention horizon; they are rejected with a reason so the app can stop retrying.
- **Short views arriving late** — a device still holding an older, lower threshold sends views
  shorter than the current minimum. These are **stored as-is**. The threshold is a client-side
  decision; re-checking it server-side would silently discard legitimate history.
- **Two devices, same person** — the same member using a phone and a tablet contributes two devices
  to the same occurrence. The occurrence is still one.
- **Nothing configured** — with zero active service windows, every view collapses by hymn plus
  calendar day. The dashboard still works.
- **View spanning a window edge** — a view is placed by its recorded start time only; a view that
  starts inside a window belongs to that window even if it runs past the end time.
- **Service runs long** — a hymn opened after the scheduled end still belongs to that service, up to
  the grace period (FR-032). Past it, the view falls back to day-collapsing.
- **Grace crossing midnight** — a late service whose grace period runs past 00:00 must not wrap
  around and stop matching; the following day is a different weekday and gets no grace from it.
- **Overlapping windows** — a view time that matches more than one active window is assigned to the
  earliest-starting matching window, so the grouping is deterministic.
- **Hymn removal** — a hymn that has recorded views cannot be deleted; history is never orphaned.
- **User removal** — deleting a user account leaves their view records in place, detached and
  counted as anonymous. History must not shrink when someone leaves the church.
- **Duplicate identifier, different content** — a record whose identifier already exists is treated
  as already-received; the stored version wins and the new payload is discarded.
- **Same identifier twice inside one batch** — the first occurrence is processed, the second is
  treated as a duplicate; both come back in `accepted`.
- **Range too wide** — a requested reporting range beyond the allowed maximum is rejected rather
  than served slowly.
- **Settings unreachable** — the app must survive this endpoint being offline at startup by using
  its last known values, or its built-in 30-second default on a fresh install. The backend
  guarantees only that the values are readable without credentials.

---

## Requirements *(mandatory)*

### Functional Requirements

#### Collection

- **FR-001**: The system MUST accept a batch of hymn view records in a single request from the app,
  because the app collects records offline and syncs them together.
- **FR-002**: The system MUST accept view records from clients with no credentials, and MUST attach
  the authenticated user when valid credentials are present. A record with no user is stored as
  anonymous and still counts.
- **FR-003**: The system MUST require a device identifier on every record, whether or not a user is
  authenticated, because collapsing and device counting depend on it.
- **FR-004**: The system MUST record, for each view: the hymn viewed, the moment it was viewed as
  reported by the device, how long it stayed open, the device, the user (or none), optionally the
  app version and platform, and the moment the record reached the server.
- **FR-005**: The system MUST treat each record's client-generated identifier as an idempotency
  key: a record whose identifier already exists MUST NOT create a second record.
- **FR-006**: The system MUST discard a new record when a record for the same hymn and the same
  device already exists within the configured collapse window of the reported view time, measured
  in either direction.
- **FR-007**: The system MUST answer each record in the batch individually, returning one list of
  identifiers the app may safely delete locally and one list of identifiers that were refused, each
  with a reason. A single bad record MUST NOT prevent the rest of the batch from being processed.
- **FR-008**: The system MUST report a record as safe to delete when it was stored, when it was a
  duplicate, and when it was collapsed — the app's local copy is disposable in all three cases.
- **FR-009**: The system MUST refuse a record whose hymn does not exist, whose reported view time is
  further in the future than the configured tolerance, or whose reported view time is older than
  the configured retention horizon — each with a reason that names the offending value.
- **FR-010**: The system MUST refuse the entire request when the batch exceeds the configured
  maximum size, so the app is told to split rather than losing records.
- **FR-011**: The system MUST NOT re-check the reported duration against the minimum-view-duration
  setting. That threshold belongs to the client, and buffered records may legitimately carry an
  older value.
- **FR-012**: The system MUST rate-limit the collection endpoint, since it accepts writes without
  credentials.
- **FR-013**: No record may end up in a state where the app must retry it forever. Every record in
  a batch MUST come back in exactly one of the two lists.

#### Reporting

- **FR-014**: The system MUST define an **occurrence** as one hymn sung once by the congregation:
  all views of the same hymn falling inside the same service window collapse into one occurrence,
  regardless of how many people or devices contributed.
- **FR-015**: The system MUST collapse views that fall outside every active service window by hymn
  plus calendar day instead.
- **FR-016**: The system MUST assign a view to a service window using the view time interpreted in
  the church's local timezone, matching the window's weekday and time range; when several active
  windows match, the earliest-starting one wins.
- **FR-017**: The system MUST expose the occurrences inside a requested date range, each reporting
  the hymn number, the hymn title, the grouping bucket it belongs to, and how many distinct devices
  contributed to it.
- **FR-018**: The system MUST support grouping the occurrences by service, day, week or month.
  Grouping affects only the reported bucket, never how occurrences are collapsed.
- **FR-019**: The system MUST expose a ranking of hymns by number of occurrences, ordered from most
  to least, covering all recorded history by default and an optional date range when supplied.
- **FR-020**: The ranking MUST count occurrences, not raw view records, and MUST omit hymns with no
  occurrences in the range.
- **FR-021**: Reporting endpoints MUST be restricted to administrators.
- **FR-022**: The system MUST reject a reporting range whose start is after its end, or whose span
  exceeds the allowed maximum, naming the offending values.
- **FR-023**: Occurrences MUST be derived at read time from the currently configured service
  windows. Changing or removing a window MUST NOT modify any stored view record.

#### Configuration

- **FR-024**: The system MUST hold exactly one set of collection settings, enforced so a second set
  cannot be created: minimum view duration, collapse window, maximum batch size, oldest accepted
  view age, future-time tolerance, and the window grace period from FR-032.
- **FR-025**: The system MUST allow reading the settings without credentials, so a fresh install
  can learn the minimum view duration before anyone logs in. The values are plain numbers with no
  sensitive content.
- **FR-026**: The system MUST restrict changing the settings to administrators, and MUST validate
  every field as a positive whole number within a defined upper bound, rejecting anything else with
  a message naming the field, the offending value and the accepted range.
- **FR-027**: Changing a setting MUST affect future behaviour only. Stored history MUST NOT be
  rewritten, re-evaluated or deleted, and records collected under an older threshold stay as they
  are.
- **FR-028**: The system MUST allow administrators to list, create, update and delete service
  windows, validating that the end time is strictly after the start time and that the weekday is
  between 0 and 6.
- **FR-029**: The system MUST ship with the church's current service windows already configured, so
  the dashboard distinguishes services from the first deploy without manual setup: Terça de Oração
  (Tue 19:30–20:30), Quinta de Oração (Thu 19:30–20:30), Escola Bíblica Dominical (Sun 09:00–10:00)
  and Culto Dominical (Sun 19:30–21:00). It MUST also remain fully functional with none configured,
  falling back to hymn plus calendar day (FR-015).
- **FR-032**: Window matching MUST extend past a window's end time by a configurable grace period
  (default 30 minutes), because services run long and a hymn sung after the scheduled end still
  belongs to that service. The **start** MUST NOT be extended — opening a hymn before the service
  begins is preparation, not singing with the congregation. Like every other setting, changing the
  grace re-interprets future reads only and never rewrites a stored event.

#### Coexistence

- **FR-030**: The existing Sunday repertoire registration and everything reading it MUST remain
  unchanged in behaviour and in response shape.
- **FR-031**: All timestamp reasoning — window matching, day, week and month boundaries — MUST use
  the church's local timezone (`America/Sao_Paulo`).

### Key Entities

- **Hymn view record**: one view of one hymn that the app counted as real. Carries the
  client-generated identifier used for idempotency, the hymn, the device, the optional user, the
  reported view time, the duration, optional app version and platform, and the server receive time.
  Belongs to exactly one hymn; a hymn with records cannot be deleted.
- **Service window**: a recurring weekly time range during which the church holds a service — a
  name, a weekday, a start and end time, and whether it is active. Owned by this feature, not read
  from the schedule domain. Used only to group view records into "the same moment".
- **Collection settings**: the single, editable set of numbers governing collection and matching —
  minimum view duration, collapse window, maximum batch size, oldest accepted view age, future-time
  tolerance, window grace period.
- **Occurrence** *(derived, not stored)*: one hymn sung once by the congregation. Identified by
  hymn plus service window, or hymn plus calendar day when no window matches. Carries the number of
  distinct devices that contributed.

---

## API Surface

All endpoints sit under the base path (`/ipbcb/`), consistent with the rest of the project.

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| POST | `/api/hymnal-history/events/` | AllowAny, throttled | Ingest a batch of view records |
| GET | `/api/hymnal-history/occurrences/` | `reports.hymnal_history` view | Occurrences in a period, grouped |
| GET | `/api/hymnal-history/top-hymns/` | `reports.hymnal_history` view | Hymn ranking by occurrence count |
| GET | `/api/hymnal-history/settings/` | AllowAny | Read collection settings |
| PATCH | `/api/hymnal-history/settings/` | `reports.hymnal_history` owner (override) | Update collection settings |
| GET/POST | `/api/hymnal-history/service-windows/` | `reports.hymnal_history` view / owner (override) | List / create service windows |
| GET/PATCH/DELETE | `/api/hymnal-history/service-windows/{id}/` | `reports.hymnal_history` view / owner (override) / owner | Read / update / delete a window |

**Ingest response** (`201`):

```json
{
  "accepted": ["<client_event_id>", "..."],
  "rejected": [{ "client_event_id": "...", "reason": "..." }]
}
```

`accepted` means "safe to delete locally" — stored, duplicate or collapsed alike. `rejected` records
are also deleted by the app, with the reason logged, so nothing retries forever.

**Query parameters**:

- `occurrences`: `from` (date), `to` (date), `group_by` = `service` | `day` | `week` | `month`
- `top-hymns`: `from` (date, optional), `to` (date, optional)

**Deliberately not built**: a "does the server already have these?" confirmation endpoint. The
client-generated identifier already provides real idempotency, so the app can simply re-send.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A leader can answer "which hymns did we sing last Sunday?" from the app in under 30
  seconds, without anyone having entered that data by hand.
- **SC-002**: A hymn sung once during a service is reported once, no matter how many members opened
  it — verified with at least 5 devices contributing to a single occurrence.
- **SC-003**: A device that has been offline for a week syncs its buffered history in a single
  sync, with 100% of records answered for and none left retrying.
- **SC-004**: Re-sending an identical batch any number of times produces exactly the same stored
  history as sending it once.
- **SC-005**: A batch of 200 records is fully processed within the app's normal sync timeout, and a
  reporting request covering a full year of history returns within the app's normal request
  timeout.
- **SC-006**: An admin changes the minimum view duration and every device picks up the new value on
  its next startup, with no app release and no server deploy.
- **SC-007**: 100% of previously stored history remains byte-identical after any settings or
  service-window change.
- **SC-008**: Existing Sunday repertoire registration and reading keeps working exactly as before —
  the current test suite for it passes unchanged.

---

## Assumptions

Reasonable defaults chosen where the description did not specify. Each is a decision, not a gap.

- **Reporting range defaults**: when `from`/`to` are omitted on the occurrences endpoint, the range
  defaults to the last 30 days; `group_by` defaults to `service`. The ranking endpoint defaults to
  all recorded history, as stated.
- **Maximum reporting span**: 366 days, so a leader can ask for a full year but not accidentally
  request everything. Beyond that the request is refused, not served slowly.
- **No pagination on reporting endpoints**: the range is bounded and the only client is the Android
  app rendering a list or a chart. Consistent with the other list endpoints in this domain, which
  are also unpaginated.
- **Windows do not cross midnight**: since the end time must be strictly after the start time, a
  late service ending after 00:00 must be modelled as two windows. The current church schedule does
  not need this.
- **View placement uses the start time only**: a view is assigned to the window containing its
  recorded view time; the duration is stored but does not extend the view across buckets.
- **Retention**: view records are kept indefinitely. This is an internal church app and the ranking
  is explicitly "all time". The maximum accepted age applies to *incoming* records only, not to
  stored ones.
- **Throttle scope**: the ingest endpoint is rate-limited per client address, at a rate generous
  enough for a whole congregation on shared church Wi-Fi to sync after a service. The exact rate is
  a technical decision for the plan.
- **Anonymous writes are accepted deliberately**: this is the first write endpoint in the project
  open to unauthenticated clients — every other AllowAny endpoint is read-only. It is accepted
  because most members use the hymnal without logging in, so requiring auth would collect a biased
  and largely empty history. Rate limiting, the required device identifier, the idempotency key and
  the strict per-record validation are the compensating controls, and the data carries nothing
  sensitive.
- **Device identifier is opaque**: it identifies an app install, not a person, and is used only for
  collapsing and counting distinct contributors. It is never exposed in reporting responses beyond
  an aggregate count.
- **Bucket label when no window matches**: under `group_by=service`, occurrences that matched no
  window report their calendar day as the bucket, labelled so a leader can tell them apart from
  real services.
- **Admin permission**: reuses the project's existing admin permission (authenticated plus admin
  profile), the same one guarding Sunday repertoire registration.
- **Seed data**: the four service windows in FR-029 are the church's real schedule, confirmed on
  2026-08-07, seeded by a data migration carrying its reason at the top of the file per the
  project's migration rules. The migration is idempotent and its reverse deletes only those four by
  name, leaving anything an admin adds later untouched.
- **Grace period, not longer end times**: rather than padding each window's `end_time`, the 30
  minutes live in a single setting applied at match time. Stored windows keep the *scheduled* times,
  which is what an admin recognises when editing them, and the tolerance is tunable in one place.
- **App-side behaviour is out of scope**: the client-side 30-second threshold, the offline buffer,
  the startup settings fetch and the fallback to a built-in default are all app responsibilities.
  This spec only guarantees the contract they rely on.

---

## Dependencies

- The existing `Hymn` model in the `songs` feature — view records reference it.
- The existing user account model — for optional attribution.
- The existing admin permission used by Sunday repertoire registration.
- The project timezone `America/Sao_Paulo`.

## Out of Scope

- Any Android app change.
- Any change to `Played`, `Song`, or the Sunday repertoire flow.
- Reading, importing from, or writing to the `schedule` feature.
- A confirmation endpoint asking the server which records it already has.
- Per-member reporting or any per-person breakdown of what an individual viewed.
- Real-time or push notification of new views.
