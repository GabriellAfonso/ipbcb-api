# Feature Specification: Church Events

**Feature Branch**: `020-church-events`

**Created**: 2026-10-21

**Status**: Draft

**Input**: User description: "Church events system (backend). The Android app shows events in the
home screen highlights carousel (one card per event, the three nearest) and on a detail screen.
Events are created and managed from the app's management area." (full request — event model,
active-window rule, ordering, visibility, `events` scope, endpoints, errors and future work — in
the `/speckit-specify` invocation that created this spec.) Contract points the request left open,
or that arrived truncated, were settled with the app's Claude Code session on 2026-10-21; see
Clarifications.

## Context

The church announces conferences, camps, special services and gatherings by word of mouth and
messaging groups. The app has no place for them. This feature adds **events**: a picture, a
title, dates and a few optional details, shown to anyone who opens the app — visitors included —
and created by the people who already run the management panel.

An event is either **public** (anyone, logged in or not) or **for members** (only users flagged
`is_member`). A members-only event is invisible to everyone else: not listed, not reachable by
id, and its image is not readable.

### Relation to other specs

- **`specs/012-feature-role-permissions/`** — `events` is already a reserved scope there
  (Admin `owner`, Liderança `manage`, Mídia `manage`). This feature raises Liderança and Mídia to
  `owner` and adds the endpoint classification (FR-024).
- **`specs/009-protected-media-access/`** and the constitution's Media section — every media file
  is served today only to authenticated callers. Public event images must load without a token,
  so this feature adds an `events/` media folder with the first rule that does not require
  authentication (FR-018 to FR-021, FR-025).
- **`specs/accounts/spec.md`** — the profile's `permissions` map already lists every defined
  scope, `events` included (012, Assumptions). This feature only gives the key real endpoints
  behind it.

## Clarifications

### Session 2026-10-21 (with the app's Claude Code session)

- Q: How do anonymous users load a public event's image, given that all media needs a token? →
  A: new media folder `events/`; a public event's image is readable without a token; a members
  event's image only by members, `404` to everyone else. The app's image loader attaches the
  token when logged in and sends none when logged out.
- Q: Truncated parts of the request? → A: `end_date` optional (absent = one-day event); the app
  crops to 16:9 before upload and the server validates; `members` = `is_member` users; past events
  stay visible in management (list and detail); a members event is `404` on the detail for
  others; `view` = read in management, `manage` = create/edit, `owner` = also delete; refusals use
  the existing canonical error; management edit is a multipart `PATCH` with the image optional.
- Q: Delete semantics? → A: hard delete, row and image file. No trash.
- Q: Image limits? → A: 10 MB, JPEG/PNG/WEBP, 16:9 within ±2%, at least 640×360 px. The server
  re-encodes to JPEG capped at 1920×1080 and does not keep the original.
- Q: Lists? → A: public list returns every active event, no limit, no pagination; management list
  takes `?status=active|past|all` (default `all`), ordered by `start_date` descending, no
  pagination.
- Q: Empty optional values? → A: `null`. The server turns blank strings into `null` on write.
- Q: Publication time? → A: an event is visible from the moment it is created; no draft, no
  scheduled publication.
- Q: Public endpoints with an invalid or expired token? → A: `401`, like every other endpoint, so
  the app refreshes the token and retries. No token at all → `200` with public events only.
- Q: Levels on `events`? → A: Admin, Liderança and Mídia all `owner`; amend 012.
- Q: Retention of past events? → A: kept forever; no purge or scheduled job; only a manual delete
  by an `owner` removes one. A members-facing "past events" screen is future work.

## Definitions

### Event dates and the active window

- `start_date` is required; `end_date` is optional and, when present, is on or after
  `start_date`. Without `end_date` the event lasts one day.
- The **last day** of an event is `end_date` if present, else `start_date`.
- An event is **active** from its creation until the end of its last day (23:59:59.999…) in the
  `America/Sao_Paulo` time zone. After that it is **past**. Being active or past is computed when
  the request is answered — nothing is stored and no scheduled job runs.
- "Today" for every rule below is the current date in `America/Sao_Paulo`, regardless of the
  server's or the phone's time zone.

### Visibility

| Visibility | Public list and detail | Event image |
|------------|------------------------|-------------|
| `public` (default) | everyone, with or without login | everyone, with or without a token |
| `members` | only users with `is_member` | only users with `is_member` |

For anyone outside the audience a `members` event does not exist: it is not listed and its
detail and image answer `404`, exactly as for an id that never existed. Roles grant nothing here —
the public endpoints and the image rule look at membership only. Management endpoints show every
event to whoever holds a level on `events`.

### Public ordering

Active events, by `start_date` ascending, then `start_time` ascending with **no time first**,
then id. An event already under way (started before today, last day today or later) is active and
therefore comes before every future event.

### Image

| Rule | Value |
|------|-------|
| Accepted formats (decoded content, not the extension) | JPEG, PNG, WEBP |
| Maximum upload size | 10 MB |
| Aspect ratio | 16:9, accepted when width ÷ height is within ±2% of 16/9 |
| Minimum dimensions | 640 × 360 px |
| Stored file | JPEG, re-encoded, downscaled to fit 1920 × 1080 (never upscaled); the uploaded original is not kept |

Each value is a single constant so it can change later. EXIF orientation is applied before the
ratio is measured; transparency is flattened onto white.

The image is stored under `events/` with a random filename. Replacing it writes a new file with a
new name, so an image URL never changes content: a cached copy stays valid for as long as that URL
is returned.

### Endpoints

| Method | Route | Access | Purpose |
|--------|-------|--------|---------|
| GET    | `api/events/` | public; token optional | active events visible to the caller |
| GET    | `api/events/{id}/` | public; token optional | one active event visible to the caller |
| GET    | `api/admin/events/` | `view` on `events` | every event, filterable by `status` |
| POST   | `api/admin/events/` | `manage` on `events` | create (multipart, image required) |
| GET    | `api/admin/events/{id}/` | `view` on `events` | one event, active or past |
| PATCH  | `api/admin/events/{id}/` | `manage` on `events` | edit (multipart, image optional) |
| DELETE | `api/admin/events/{id}/` | `owner` on `events` | delete event and image file |

Levels are the method defaults of 012; no override.

### Event resource (public)

```json
{
  "id": 12,
  "title": "Congresso de Jovens",
  "start_date": "2026-11-14",
  "end_date": "2026-11-16",
  "start_time": "19:30",
  "location": "Templo principal",
  "description": "Três noites de louvor e palavra…",
  "image_url": "http://host/ipbcb/media/events/8c41….jpg",
  "visibility": "public"
}
```

- `end_date`, `start_time` (`"HH:MM"`), `location`, `description`: `null` when absent.
- `image_url`: absolute URI.

### Event resource (management)

The public resource plus:

```json
{
  "created_by": { "id": "5b0e…-uuid", "name": "Ana Paula" },
  "updated_by": { "id": "a71d…-uuid", "name": "Beatriz" },
  "created_at": "2026-10-21T13:02:11Z",
  "updated_at": "2026-10-22T09:40:00Z"
}
```

`created_by` is `null` when the creating account no longer exists. `updated_by` — same shape —
is who made the last successful edit: `null` for an event never edited and when that account no
longer exists.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Anyone sees upcoming events on the home screen (Priority: P1)

A visitor opens the app without an account. The highlights carousel shows the next church
events, each with its picture, title and date; tapping one opens its detail.

**Why this priority**: This is what the feature is for. Without the public read nothing reaches
the congregation.

**Independent Test**: Seed a past, an ongoing and two future public events; list without a
token; the ongoing and future ones come back in order and each image URL loads without a token.

**Acceptance Scenarios**:

1. **Given** public events A (yesterday to tomorrow), B (in 3 days, 19:30), C (in 3 days, no time)
   and D (last week), **When** an anonymous caller lists events, **Then** the answer is `200` with
   A, C, B in that order and no D.
2. **Given** a one-day public event dated today, **When** it is listed at 23:59 São Paulo time,
   **Then** it is present; **When** listed at 00:00 of the next day, **Then** it is absent — with
   no write to the database in between.
3. **Given** an active public event, **When** an anonymous caller reads its detail, **Then** the
   answer is `200` with the public resource.
4. **Given** a past public event, **When** anyone reads its public detail, **Then** the answer is
   `404`.
5. **Given** a public event, **When** its `image_url` is requested without a token, **Then** the
   image is served.
6. **Given** no active events, **When** the list is read, **Then** the answer is `200 []`.

---

### User Story 2 - Members also see members-only events (Priority: P1)

A logged-in member sees, mixed into the same carousel, events meant only for the congregation —
a members' assembly, for example. Visitors and logged-in non-members never learn they exist.

**Why this priority**: Visibility is a privacy promise; getting it wrong leaks internal events.

**Independent Test**: Seed one public and one members event, both active; read list, detail and
image as anonymous, as a non-member with a role, and as a member.

**Acceptance Scenarios**:

1. **Given** an active `members` event, **When** a member lists events, **Then** it appears,
   ordered among public events by the public ordering.
2. **Given** the same event, **When** an anonymous caller or a logged-in non-member lists events,
   **Then** it is absent.
3. **Given** the same event, **When** a non-member reads its detail or its image, **Then** the
   answer is `404`, identical to an id that never existed.
4. **Given** a non-member who holds `owner` on `events`, **When** they use the **public**
   endpoints, **Then** the `members` event is still hidden — roles grant nothing there.
5. **Given** a request with an expired or malformed token, **When** it reaches either public
   endpoint, **Then** the answer is `401`.

---

### User Story 3 - The panel creates an event (Priority: P1)

Someone from the media team crops a poster to 16:9 in the app, fills in the title, dates and
place, and publishes. The event shows in the carousel right away.

**Why this priority**: Without creation there is nothing to show; today no other tool does it.

**Independent Test**: As a Mídia user, create an event with only the required fields and a valid
image; it appears in the public list immediately with a JPEG image within 1920 × 1080.

**Acceptance Scenarios**:

1. **Given** a Mídia user, **When** they create an event with `title`, `start_date` and a 16:9
   image, **Then** the answer is `201` with the management resource, `visibility` `public`, every
   optional field `null`, `created_by` set to them and `updated_by` `null`.
2. **Given** a 4000 × 2250 PNG, **When** it is uploaded, **Then** the stored image is a JPEG of
   1920 × 1080; **given** a 1280 × 720 JPEG, **Then** it is stored at 1280 × 720.
3. **Given** an image of 1600 × 1000 (ratio 1.6), **When** it is uploaded, **Then** the answer is
   `400` with a field error on `image` naming the received ratio and the expected 16:9 ± 2%.
4. **Given** an image of 1000 × 563 (ratio 1.776, within tolerance), **When** it is uploaded,
   **Then** it is accepted.
5. **Given** an image smaller than 640 × 360, larger than 10 MB, or not a JPEG/PNG/WEBP by
   content, **When** it is uploaded, **Then** the answer is `400` with a field error on `image`.
6. **Given** a blank `title`, a missing `start_date`, a missing image, or an `end_date` before
   `start_date`, **When** the event is created, **Then** the answer is `400` with one field error
   per offending field and nothing is stored.
7. **Given** `location` or `description` sent as blank or whitespace-only text, **When** the
   event is saved, **Then** they are stored as absent and returned as `null`.
8. **Given** a user without any level on `events` — a member included — **When** they create an
   event, **Then** the answer is `403` `PERMISSION_DENIED`.

---

### User Story 4 - The panel edits and deletes events (Priority: P2)

The date of the camp moves, or the poster changes; someone fixes it in the app. A cancelled event
is deleted.

**Why this priority**: Mistakes and changes are routine, but creation alone already delivers
value.

**Independent Test**: PATCH an event's `end_date` and image; its old image URL stops resolving
and a new one is returned. DELETE it; it disappears from both lists and its image is gone.

**Acceptance Scenarios**:

1. **Given** an event, **When** a `PATCH` changes only `location`, **Then** only `location`,
   `updated_at` and `updated_by` change and the `image_url` is the same.
2. **Given** an event, **When** a `PATCH` carries a new image, **Then** the image is validated
   like on creation, the response has a new `image_url`, and the previous image file is removed.
3. **Given** a `PATCH` whose new image is invalid, **When** it is sent, **Then** the answer is
   `400` and neither the event nor its image changes.
4. **Given** an event with `start_date` 10 and no `end_date`, **When** a `PATCH` sets only
   `end_date` 8, **Then** the answer is `400` — the rule is checked on the resulting event, not on
   the sent fields alone.
5. **Given** an event with an `end_date`, **When** a `PATCH` sets `end_date` to `null`, **Then**
   it becomes a one-day event.
6. **Given** a `PATCH` that changes `visibility` from `public` to `members`, **When** a
   non-member reads the list, detail or image afterwards, **Then** the event is hidden.
7. **Given** an event, **When** an Admin, Liderança or Mídia user deletes it, **Then** the answer
   is `204`, the event is gone from every endpoint and its image file no longer exists.
8. **Given** a user with only `view` or `manage` on `events`, **When** they delete, **Then** the
   answer is `403`.
9. **Given** a nonexistent id, **When** it is read, edited or deleted through management,
   **Then** the answer is `404`.
10. **Given** an event created by one user, **When** another user's `PATCH` succeeds — even one
    that sends no field — **Then** `updated_by` is that user and `created_by` is unchanged; a
    refused `PATCH` leaves `updated_by` as it was; once the editor's account is deleted,
    `updated_by` is `null` and the event stays.

---

### User Story 5 - The panel reviews all events, past included (Priority: P2)

The management area lists every event — upcoming first to check what is published, or past ones
to reuse a description.

**Why this priority**: Managers need to find an event to edit or delete it, including ones the
public no longer sees.

**Independent Test**: Seed active and past events of both visibilities; list with each `status`
value and compare.

**Acceptance Scenarios**:

1. **Given** active and past events of both visibilities, **When** a `view` user lists without a
   filter, **Then** every event is returned, by `start_date` descending, then `start_time`
   descending with no time last, then id descending.
2. **Given** the same events, **When** listed with `status=active` or `status=past`, **Then**
   only events in that state are returned, in the same order.
3. **Given** an unknown `status` value, **When** the list is read, **Then** the answer is `400`
   naming the value and the accepted ones.
4. **Given** a past `members` event, **When** a management user who is not a member reads its
   management detail, **Then** it is returned — management ignores visibility.

---

### Edge Cases

- **Event under way.** A camp from Friday to Sunday is active on all three days and sorts by its
  `start_date`, so on Saturday it comes before an event starting Sunday.
- **Time zone boundary.** At 02:30 UTC it is still the previous day in São Paulo (UTC−3); an event
  whose last day is that previous day is still active. "Today" never comes from the server clock's
  zone or from the request.
- **Creating an event already past.** Allowed (e.g. to record what happened); it shows only in
  management with `status=past`/`all`.
- **`start_time` without date semantics.** It is only for display and the tie-break; it does not
  shorten the active window (an event at 08:00 stays active until the end of the day).
- **Same date, same time.** Ties fall back to id, so the order is deterministic.
- **Image ratio after EXIF rotation.** A portrait photo tagged to display as landscape is measured
  as displayed. A 16:9 image stored rotated in pixels but displayed upright as 9:16 is rejected.
- **Token present but no profile row.** Treated as a non-member: public events only.
- **Image file missing on disk** (removed by hand): the event still lists; the image URL answers
  `404`. Accepted, like orphans elsewhere.
- **Failed write after the image was saved.** The new file is removed; no orphan image is kept on
  a failed create or edit, and the old image is kept on a failed edit.
- **Image request for a file under `events/` with no event row** (deleted event, stale cached
  URL, guessed name): `404` to everyone.
- **Media path rules.** Traversal, encoding and default-deny rules of 009 apply to `events/`
  unchanged; only the folder rule is new.
- **Concurrent edit.** Last write wins; there is no change history (012 accepted risk).
- **Several images per request or a field named differently**: only the `image` field is read;
  others are ignored.

## Requirements *(mandatory)*

### Functional Requirements

**Event data**

- **FR-001**: An event MUST have a `title` (required, trimmed, not blank, at most 120
  characters), a `start_date` (required), an optional `end_date` on or after `start_date`, an
  optional `start_time` (hour and minute), an optional `location` (at most 200 characters), an
  optional `description` (long text), a required image, and a `visibility` of `public` (default)
  or `members`.
- **FR-002**: An event MUST record who created it, when, who last edited it, and when it was
  last changed. These fields are set by the system, never from input. Every successful edit
  records its caller as the last editor, even one that sends no field; an event never edited has
  no last editor.
- **FR-003**: Blank or whitespace-only `location` and `description` MUST be stored as absent and
  returned as `null`.
- **FR-004**: The date rule (`end_date` ≥ `start_date`) MUST be checked on the resulting event for
  partial edits.

**Active window and ordering**

- **FR-005**: An event MUST count as active from creation until the end of its last day in
  `America/Sao_Paulo`, computed at read time with no stored state and no scheduled job.
- **FR-006**: The public list MUST return every active event visible to the caller, ordered by
  `start_date` ascending, then `start_time` ascending with absent times first, then id. No limit
  and no pagination.
- **FR-007**: The management list MUST return every event, filtered by `status` (`active`,
  `past`, `all`; default `all`), ordered by `start_date` descending, then `start_time` descending
  with absent times last, then id descending. No pagination. An unknown `status` MUST be `400`.

**Visibility**

- **FR-008**: The public endpoints MUST work without authentication. A caller without a token, or
  whose account is not a member, MUST see only `public` events; a member MUST see `public` and
  `members` events.
- **FR-009**: A request to a public endpoint carrying an invalid or expired token MUST be `401`.
- **FR-010**: A `members` event MUST be indistinguishable from a nonexistent one for a non-member:
  absent from the list, `404` on the detail and on its image, with the same body.
- **FR-011**: The public detail of a past event MUST be `404`.
- **FR-012**: Roles and levels MUST NOT affect what the public endpoints return.

**Management and permissions**

- **FR-013**: Every management endpoint MUST declare scope `events` with the method's default
  level (`view` for reads, `manage` for create and edit, `owner` for delete), and refuse a caller
  without it with `403` `PERMISSION_DENIED` before any business logic runs.
- **FR-014**: Admin, Liderança and Mídia MUST hold `owner` on `events` after the deploy, with no
  manual step. Liderança and Mídia are raised by a data migration whose reason is documented at
  the top of the file.
- **FR-015**: Management reads MUST return events regardless of visibility and of being active or
  past.
- **FR-016**: Delete MUST remove the event and its image file permanently.
- **FR-016a**: Past events MUST be kept indefinitely, image included. Nothing purges them
  automatically; only a delete by an `owner` removes an event.

**Image**

- **FR-017**: The image MUST be validated by decoded content against the Image table (format,
  size, ratio, minimum dimensions), after applying EXIF orientation, and stored re-encoded as JPEG
  fitted within 1920 × 1080 under `events/` with a random filename. The original MUST NOT be kept.
- **FR-018**: Replacing an image MUST store a new file under a new name and remove the previous
  file once the edit is saved.
- **FR-019**: Files under `events/` MUST be readable through the media access check by: anyone,
  with or without a token, when the file is the image of a `public` event; members only when it is
  the image of a `members` event. Every other case — non-member on a `members` image, a file with
  no event — MUST be `404`.
- **FR-020**: The `events/` rule MUST decide with one indexed lookup of the file's event, after
  path validation; an invalid token on an `events/` request MUST still be `401`.
- **FR-021**: `events/` responses MUST follow the media cache contract (`private, no-cache`,
  validators from nginx, `304` on unchanged files).

**Errors**

- **FR-022**: Validation errors MUST be `400` in the canonical shape with one field error per
  offending field (`title`, `start_date`, `end_date`, `image`, `visibility`, `start_time`), each
  message in Portuguese naming the received value and the expected shape.
- **FR-023**: A nonexistent event, on any endpoint, MUST be `404` in the canonical shape.

**Specs**

- **FR-024**: `specs/012-feature-role-permissions/spec.md` MUST be amended: `events` row of the
  scope matrix (Liderança and Mídia `owner`), the "events and notices are future features" note,
  FR-009 ("Leader MUST NOT hold `owner` on any scope except `gallery`"), SC-002, User Story 2, the
  "Leader + Media on `events` is `manage`" edge case, and a new `events` section in Endpoint
  Classification.
- **FR-025**: `specs/009-protected-media-access/spec.md` (FR-002, FR-005, FR-009) and the
  constitution's Media section MUST record the `events/` folder as the one rule that does not
  require authentication, and why.
- **FR-026**: A domain spec `specs/events/spec.md` MUST describe the domain as this feature leaves
  it, including the Future section below.

### Key Entities

- **Event**: title, start date, optional end date, optional start time, optional location,
  optional description, image, visibility, creator, last editor, creation and update
  timestamps. Active or past is derived, never stored.
- **Event image**: one re-encoded JPEG per event, under `events/`, replaced as a whole.
- **Scope `events`** (existing, reserved by 012): now backed by endpoints; all three roles hold
  `owner`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A visitor with no account sees every active public event, with its image, on the
  first open of the app — 0 public events or images require logging in.
- **SC-002**: 0 members-only events, details or images are obtainable by anonymous callers or
  non-members, across every endpoint; each path is covered by an automated check.
- **SC-003**: An event disappears from the public list within the first request after the end of
  its last day in São Paulo time, with no manual action and no scheduled job.
- **SC-004**: The media team publishes an event entirely from the phone, and it is visible to the
  public on the next list read.
- **SC-005**: 100% of stored event images are JPEG, 16:9 within ±2%, at most 1920 × 1080 — so a
  carousel card never downloads more than one such file.
- **SC-006**: For every role (Admin, Liderança, Mídia, none) × management method, the outcome
  matches the matrix — each combination covered by an automated check.

## Assumptions

- **Field limits** (`title` 120, `location` 200 characters) are chosen here; the request set
  none. They fit a carousel card and a detail line.
- **No-time-first ordering** on the public list (decided with the app) — an all-day event is shown
  before timed ones on the same date. Management, ordered descending, puts no-time last.
- **`start_time` is a time of day only**, without time zone; it is read as São Paulo local time.
- **Membership is `Profile.is_member`**, read on each request; a revoked member loses the members
  events on the next request, cached images included (media revalidation).
- **No change history** for events beyond `created_by`/`updated_by`/`created_at`/`updated_at`.
- **Implementation choices recorded for planning, not decided here**: a new `features/events`
  app; image processing behind the existing image-processing interface used by the gallery; the
  `events/` rule added to the media access service with an anonymous path; public endpoints with
  optional authentication. These belong in `plan.md`.

## Out of Scope (Future)

Recorded so later features find the intent:

- **Push notification** (FCM) when an event is published.
- **"Add to calendar"** button in the app.
- **Registration link** per event.
- **"All events" screen** in the app (the public list already returns every active event).
- **"Past events" screen for members** in the app. Past events are kept (FR-016a) so it can be
  built later; today only management reads them.
- Android app changes (separate repository).
- Draft events, scheduled publication, recurring events, trash/restore.
