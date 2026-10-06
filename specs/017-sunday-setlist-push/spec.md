# Feature Specification: Sunday Worship Setlist with Push Distribution

**Feature Branch**: `017-sunday-setlist-push`

**Created**: 2026-10-01

**Status**: Draft

**Input**: User description: "Repertório do domingo do ministério de Louvor: salvar o repertório,
distribuir por push (FCM) e lembrar de confirmar as músicas tocadas." (full request — context,
business rules and error list — in the `/speckit-specify` invocation that created this spec.)

## Context

Today the app builds a Sunday repertoire from the song suggestions (`GET /api/suggested-songs/`)
and, after the service, someone registers what was actually played
(`POST /api/played/register/`). Between those two moments nothing is stored on the server: the
setlist the worship leader chose lives only on that leader's phone and reaches the band by
word of mouth. Nothing reminds anyone to register the played songs, so Sundays go unrecorded
and the suggestion history — which excludes songs played in the last 90 days — drifts from
reality.

This feature stores the Sunday setlist on the server, delivers it to every worship ministry
member's phone by push notification, and nudges the people responsible to confirm the played
songs on Sunday night until someone does.

### Relation to other specs

- **`specs/songs/spec.md`** — the domain spec; gains the setlist entity, its endpoints and its
  errors. `Played` and `POST /api/played/register/` are unchanged: a registered play is what
  stops the reminder and clears a pending confirmation.
- **`specs/accounts/spec.md`** — the profile gains the two worship flags, and the account gains
  its device push tokens.
- **`specs/members/spec.md`** — the source of ministry membership (`Member.ministries`) and of
  the profile ↔ member link (`Profile.member`). The members domain holds sensitive data
  (constitution, Security): nothing here exposes member fields beyond the caller's own flags.
- **`specs/012-feature-role-permissions/`** — roles and scope levels used for authorization.
- **`specs/001-api-error-handling/`** — every refusal uses the canonical error shape.
- **`specs/002-structured-json-logging/`** — push outcomes and reminder runs are logged in its
  format.

## Clarifications

### Session 2026-10-01

- Q: The request says "papel admin ou leader" to save and "admins" to read by date and list
  pending confirmations, but the constitution says levels come from roles only through scopes.
  Authorize by role name or by scope level? → A: by scope level. Saving requires `manage` on
  scope `songs` (today Admin and Liderança) plus worship membership; reading by date and listing
  pending confirmations require `manage` on `songs` — whoever can register plays can see what is
  left to register (FR-002, FR-022, FR-023).
- Q: "Usuários admin E membros do Louvor" for the reminder — union or intersection? → A:
  neither: recipients are users who can register plays (`manage` on `songs`) AND are worship
  members — the same rule as saving, so the reminder reaches exactly who can resolve it (FR-017).
- Q: Assumptions listed below? → A: accepted as written.

### Session 2026-10-06

- Q: Who may delete a setlist? → A: exactly who may save it — `manage` on `songs` AND worship
  member. `DELETE` defaults to `owner`, so the endpoint lowers it explicitly (listed in
  `specs/012-feature-role-permissions/spec.md`, Lowered overrides) (FR-026).
- Q: Push on delete? → A: no. The app re-reads `current/` on start and resume and treats
  `{"setlist": null}` as deleted (FR-027).
- Q: Is a setlist kept forever? → A: no, it serves one Sunday. A daily job deletes setlists
  confirmed (plays registered) more than 30 days ago, and unconfirmed ones more than 90 days
  ago — by then nobody will register them, and the pending card must not grow forever (FR-028).

## Definitions

### Worship ministry

The ministry whose name is **"Louvor"**, compared case-insensitively and ignoring surrounding
whitespace. The name is a constant in the backend; ministry ids are never used to identify it,
because ids can change when ministries are recreated in the Django admin.

### Worship member

A user whose profile is linked to a member of the church roll, and that member belongs to the
worship ministry. A user without a linked member is never a worship member, whatever their
roles.

### Setlist

The songs chosen for one Sunday's service: a date (always a Sunday), an ordered list of items
(position, song, key), who saved it and when. At most one setlist exists per date.

### Current setlist

The setlist with the earliest date that is on or after today, "today" being the calendar date in
`America/Sao_Paulo`. On a Sunday, that Sunday's setlist stays current until midnight.

### Played songs registered for a date

At least one `Played` row exists with that date, regardless of who registered it or whether it
matches the setlist.

### Reminder window

Each half hour of the setlist's Sunday from 21:00 to 23:30 inclusive, `America/Sao_Paulo`:
21:00, 21:30, 22:00, 22:30, 23:00, 23:30 — at most six reminders per setlist. A window runs
from its start until the next window's start (the 23:30 window until midnight).

### Device token

The push registration token one installation of the app receives from the push provider. One
token per device; a token belongs to the user last signed in on that device.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Worship leader saves the Sunday setlist (Priority: P1)

A worship leader picks the songs for next Sunday in the app (starting from the suggestions or
not) and saves them: date, songs in order, and the key of each. The server keeps it as that
Sunday's setlist. If they notice a mistake, they save again for the same date and the new list
replaces the old one entirely.

**Why this priority**: every other story depends on a setlist existing on the server.

**Independent Test**: save a setlist as a leader in the worship ministry, read it back by date,
save a different one for the same date, and check only the second remains.

**Acceptance Scenarios**:

1. **Given** a user with `manage` on `songs` who is a worship member, **When** they save a setlist
   for a Sunday with valid songs and unique positions, **Then** it is stored with the caller as
   author and the save time, and the answer contains the stored setlist.
2. **Given** a setlist already saved for that Sunday, **When** an authorized user saves again for
   the same date, **Then** the old items are gone, only the new items remain, and author and
   save time reflect the new save.
3. **Given** a date that is not a Sunday, **When** the setlist is saved, **Then** it is refused
   with `400` naming the date and its weekday, and nothing is stored.
4. **Given** an empty item list or two items with the same position, **When** saved, **Then**
   `400`, nothing stored.
5. **Given** an item referencing a song that does not exist, **When** saved, **Then** `404`
   listing the missing song ids, nothing stored.
6. **Given** a user without `manage` on `songs`, or with it but not a worship member, **When**
   they save, **Then** `403` and nothing stored.
7. **Given** a saved setlist, **When** an authorized user deletes it, **Then** `204`, the setlist
   and its items are gone, it leaves the current setlist and the pending list, and the played
   songs of that date are untouched. No push is sent.
8. **Given** no setlist for the date, **When** an authorized user deletes it, **Then** `404`.
9. **Given** a user without `manage` on `songs`, or with it but not a worship member, **When**
   they delete, **Then** `403` and nothing is deleted.

---

### User Story 2 - Worship members receive the setlist by push (Priority: P1)

As soon as a setlist is saved (first time or a correction), every device of every worship member
— the author included — gets a data push saying "a setlist was saved for this date". The app
fetches and shows it. If the push never arrives, the app asks the server for the current setlist
on its own.

**Why this priority**: distribution is the reason to store the setlist at all; without it the
band still depends on word of mouth.

**Independent Test**: with a fake push sender, save a setlist and check one message of type
`setlist_saved` with the date was addressed to each registered device of each worship member and
to no one else; then read the current setlist as a worship member.

**Acceptance Scenarios**:

1. **Given** three worship members with registered devices and one non-worship user with a
   registered device, **When** a setlist is saved, **Then** each worship member device receives
   one `setlist_saved` message carrying the date, and the non-worship device receives none.
2. **Given** a setlist is saved again for the same date, **When** the save succeeds, **Then** the
   push is sent again.
3. **Given** the push provider is unreachable or rejects the request, **When** a setlist is
   saved, **Then** the save still succeeds and the failure is logged.
4. **Given** the provider reports a token as no longer registered, **When** the push is sent,
   **Then** that token is deleted and later pushes skip it.
5. **Given** setlists exist for last Sunday and for next Sunday, **When** a worship member asks
   for the current setlist on a weekday, **Then** they get next Sunday's.
6. **Given** no setlist on or after today, **When** a worship member asks for the current
   setlist, **Then** they get an explicit "no current setlist" answer, not an error.
7. **Given** a user who is not a worship member, **When** they ask for the current setlist,
   **Then** `403`.

---

### User Story 3 - Devices register and unregister for push (Priority: P1)

On login, and whenever the push provider rotates the device's token, the app sends the token to
the server. On logout it asks the server to forget it. The server keeps one entry per token,
owned by the user who registered it last.

**Why this priority**: without registered devices no push reaches anyone.

**Independent Test**: register a token, register it again from another user, unregister it, and
check ownership and existence at each step.

**Acceptance Scenarios**:

1. **Given** an authenticated user, **When** they register a token, **Then** it is stored for
   them; registering the same token again stores nothing new.
2. **Given** a token registered by user A, **When** user B registers the same token (same phone,
   different account), **Then** the token now belongs to B only, so A's pushes no longer reach
   that phone.
3. **Given** a registered token, **When** its owner unregisters it, **Then** it is deleted;
   unregistering a token that does not exist, or belongs to someone else, changes nothing and
   still answers success.
4. **Given** an unauthenticated caller, **When** they register or unregister, **Then** `401`.

---

### User Story 4 - The app knows what the user can do (Priority: P2)

The app shows the "save setlist" action only to users who can save, and the worship screens only
to worship members. It reads both facts from the user's profile.

**Why this priority**: the server enforces the rules either way; this only keeps the app from
offering actions that will be refused.

**Independent Test**: read the profile as users in each combination of role and ministry and
check both flags.

**Acceptance Scenarios**:

1. **Given** a user with `manage` on `songs` who is a worship member, **When** they read their
   profile, **Then** `can_save_setlist` and `is_worship_member` are both true.
2. **Given** a worship member without `manage` on `songs`, **Then** `can_save_setlist` is false and
   `is_worship_member` true.
3. **Given** a user with `manage` on `songs` whose profile has no linked member, **Then** both are
   false.
4. **Given** the user's ministries or roles change, **When** they read the profile again,
   **Then** the flags reflect the change (the profile's ETag changes with them).

---

### User Story 5 - Sunday night reminder to confirm the played songs (Priority: P2)

On the setlist's Sunday, from 21:00 and every half hour until midnight, the people responsible
— worship members who can register plays — get a data push of type `confirm_plays` with the
date — but only while no played songs are
registered for that date. Once anyone registers them, the reminders stop.

**Why this priority**: it fixes the gap that motivates the feature (unrecorded Sundays), but the
setlist is already useful without it.

**Independent Test**: with a fake clock and a fake push sender, run the reminder at 20:59, 21:05,
21:10, 21:35 and 22:01 on a Sunday with a setlist and no plays; then register plays and run at
22:31. Expect sends at 21:05, 21:35 and 22:01 only.

**Acceptance Scenarios**:

1. **Given** a setlist for today (Sunday) and no played songs for today, **When** the reminder
   runs at 21:05, **Then** recipients receive one `confirm_plays` message with the date.
2. **Given** the 21:00 window was already sent, **When** the reminder runs again at 21:20 — even
   after the process restarted — **Then** nothing is sent.
3. **Given** played songs are registered for today, **When** the reminder runs in any later
   window, **Then** nothing is sent.
4. **Given** no setlist for today, or today is not a Sunday, or it is before 21:00, **When** the
   reminder runs, **Then** nothing is sent.
5. **Given** the process was down from 21:00 to 22:40, **When** it runs at 22:40, **Then** it
   sends once, for the 22:30 window only; missed windows are not sent retroactively.
6. **Given** the push provider fails, **When** the reminder runs, **Then** the failure is logged
   and the window is still recorded as attempted, so a broken provider is not retried every few
   minutes within the same window.

---

### User Story 6 - Managers see Sundays pending confirmation (Priority: P3)

The admin panel in the app shows a card listing setlists whose Sunday has arrived but whose
played songs were never registered, so missing Sundays can be caught up. The setlist's items let
the app pre-fill the register-played form. Anyone who can register plays (`manage` on `songs`)
sees the card and can also read any setlist by date for the same pre-fill.

**Why this priority**: catch-up for the cases the reminder did not resolve.

**Independent Test**: create setlists for three past Sundays and today, register plays for one,
and check the list holds the other three, newest first.

**Acceptance Scenarios**:

1. **Given** setlists dated on or before today without registered plays, **When** a `songs` manager
   user lists pending confirmations, **Then** each appears once, newest first, with its items.
2. **Given** plays are registered for one of them, **When** the list is read again, **Then** it
   no longer appears.
3. **Given** a future setlist, **Then** it never appears in the list.
4. **Given** a user with `manage` on `songs`, **When** they read the setlist of a given date, **Then** they
   get it, or `404` when none exists for that date.
5. **Given** a user without `manage` on `songs`, **When** they list pending confirmations or read
   by date, **Then** `403`.

---

### Edge Cases

- **The "Louvor" ministry does not exist or was renamed**: nobody is a worship member; saving is
  refused with `403` for everyone, the current-setlist read is refused, and save pushes reach
  nobody, and so do reminders, since their recipients must be worship members too. Pending
  confirmations and read-by-date keep working. Logged as a warning on every push or reminder
  run that finds no worship ministry, so the rename is noticed.
- **Two ministries match "louvor" case-insensitively**: membership in either counts.
- **Saving a setlist for a past Sunday**: allowed (late correction); the push is sent and the
  setlist enters the pending list if it has no plays.
- **Two authorized users save the same date concurrently**: one setlist remains, entirely one
  save's items or entirely the other's — never a mix.
- **A worship member with no registered device**: nothing is sent to them; the save succeeds.
- **Played songs registered for a date with no setlist**: unaffected; no setlist, no reminder,
  nothing pending.
- **A worship member has several devices**: each registered device gets its own message.
- **A token is rejected as invalid by the provider in a reminder run**: deleted exactly as on a
  save push.
- **Push credentials are not configured** (e.g. development): pushes are skipped with a logged
  warning; save, reads and reminders otherwise behave normally.
- **The same song appears twice in a setlist**: accepted; only positions must be unique.
- **Malformed body** (not a JSON object, item not an object, non-integer id or position):
  `400`, never a `500` (constitution, Data Integrity).

## Requirements *(mandatory)*

### Functional Requirements

**Setlist**

- **FR-001**: The system MUST store at most one setlist per date, with its ordered items
  (position, song, key), the user who saved it last and when.
- **FR-002**: Saving MUST be allowed only to users who hold `manage` on scope `songs` (today
  Admin and Liderança, `specs/012-feature-role-permissions/`) AND are worship members; any other
  authenticated user gets `403`. Roles are never checked by name: worship membership only
  narrows who may save, it never grants a level (constitution, Authentication & Authorization).
- **FR-003**: The date MUST be a Sunday; otherwise `400` whose detail names the date received and
  its weekday.
- **FR-004**: The item list MUST be non-empty; each item MUST carry a song id, a position from 1
  to 10 and a key of 1 to 3 characters; positions MUST be unique within the setlist. Violations
  answer `400` naming the offending value and the expected shape.
- **FR-005**: Every referenced song MUST exist; otherwise `404` listing the missing ids
  (`NOT_FOUND`), consistent with `POST /api/played/register/` today.
- **FR-006**: Saving for a date that already has a setlist MUST replace its items entirely and
  update author and save time, atomically: a failed save leaves the previous setlist intact.
- **FR-007**: A successful save MUST answer with the stored setlist: date, items ordered by
  position (position, song id, title, artist, key), author's display name, save time.
- **FR-026**: Users allowed to save (FR-002) MUST be able to delete the setlist of a date, with
  its items; `204` without body, `404` when none exists for that date, `400` for a malformed
  date. `Played` rows are never affected. Each deletion is logged as `setlist_deleted` with the
  date and the user id.
- **FR-027**: Deleting MUST NOT send a push; the app learns of it from the current-setlist read
  (FR-012) on start and resume.
- **FR-028**: A daily job MUST delete, with their items, setlists dated more than 30 days before
  today (`America/Sao_Paulo`) that have played songs registered for their date, and setlists
  dated more than 90 days before today that have none. `Played` rows are never affected. Each
  run logs `setlist_purged` with the number deleted and both cutoffs. It runs in the existing
  daily `ipbcb_token_flush` loop in `compose.prod.yml`; no task queue, no host cron.

**Distribution**

- **FR-008**: After every successful save, the system MUST send a data message of type
  `setlist_saved` carrying the date (`YYYY-MM-DD`) to every registered device of every worship
  member, the author included.
- **FR-009**: A failure to send — provider unreachable, rejected, missing credentials — MUST NOT
  fail or roll back the save. Each failure is logged with the outcome and the number of devices
  affected; logs carry user ids, never member fields.
- **FR-010**: Tokens the provider reports as no longer registered (`UNREGISTERED` or
  `NOT_FOUND`) MUST be deleted, on any push, save or reminder.
- **FR-011**: Push messages MUST carry only the type and the date — no song, member or user data.
- **FR-012**: Worship members MUST be able to read the current setlist; when none exists, the
  answer says so explicitly without being an error. Non-worship users get `403`.

**Device tokens**

- **FR-013**: An authenticated user MUST be able to register a device token. A token is stored
  once; registering a token already stored moves it to the caller.
- **FR-014**: An authenticated user MUST be able to unregister a token they own; unregistering an
  unknown token or one owned by another user changes nothing and answers success, so the app's
  logout never fails on it.
- **FR-015**: Tokens MUST be validated as non-empty strings of bounded length before storage.

**Profile flags**

- **FR-016**: The user's profile MUST expose `is_worship_member` and `can_save_setlist`, computed
  on every read from the current roles, profile ↔ member link and ministries. The profile ETag
  MUST change when either flag changes.

**Reminder**

- **FR-017**: A scheduled job MUST, for today's setlist (Sunday, `America/Sao_Paulo`), send a
  data message of type `confirm_plays` with the date to every registered device of the reminder
  recipients, once per reminder window, only while no played songs are registered for that date.
  Recipients are users who hold `manage` on scope `songs` AND are worship members — the same
  rule as saving (FR-002), so the reminder reaches exactly the people who can register the
  played songs.
- **FR-018**: The job MUST record, per setlist, the last reminder window it sent, and MUST NOT
  send a window already recorded — across restarts and concurrent runs.
- **FR-019**: The job MUST send only the current window; windows missed while it was not running
  are never sent late.
- **FR-020**: A provider failure in a reminder run MUST still record the window, and MUST be
  logged.
- **FR-021**: The job MUST run as a long-lived loop invoking a management command at an interval
  short enough that each window is sent within its first few minutes, following the
  `ipbcb_token_flush` service in `compose.prod.yml`. No task queue is added.

**Pending confirmations and admin reads**

- **FR-022**: Users with `manage` on scope `songs` MUST be able to list setlists dated on or
  before today with no played songs registered for their date, newest first, each with its
  items. Worship membership is not required: this is the register-played side, not the band's.
- **FR-023**: Users with `manage` on scope `songs` MUST be able to read the setlist of a given
  date; `404` when none exists. Others get `403`.

**Configuration and security**

- **FR-024**: Push provider credentials MUST come from environment variables only; nothing
  secret is committed. Only the services that send pushes (the server and the reminder job) read
  them.
- **FR-025**: Every endpoint in this feature MUST require authentication; responses that depend
  on the caller MUST be declared private (constitution, Caching).

### Key Entities

- **Setlist**: one per date (a Sunday). Date, author (user, kept nullable if the user is
  deleted), saved at, last reminder window sent (empty until the first reminder). Transient:
  deleted 30 days after its Sunday once confirmed, 90 days after if never confirmed (FR-028).
- **Setlist item**: belongs to one setlist. Position (1-10, unique within the setlist), song
  (existing song; a song referenced by a setlist cannot be deleted), key.
- **Device token**: token string (unique), owning user, registered/updated at. Deleted on
  logout, on provider rejection, or with its user.
- **Worship ministry** (existing `members.Ministry`, matched by name) and **Played** (existing
  `songs.Played`, read only to decide reminders and pending confirmations).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A worship member sees a newly saved setlist on their phone within 1 minute of the
  save in at least 95% of saves, without opening the app first.
- **SC-002**: A save completes for the leader in under 3 seconds even when the push provider is
  down.
- **SC-003**: No recipient ever receives the same reminder window twice, including across job
  restarts.
- **SC-004**: Zero reminders are sent after played songs are registered for that date (beyond a
  run already in progress).
- **SC-005**: Within two months of release, at least 90% of Sundays that had a setlist also have
  played songs registered by the following Monday.
- **SC-006**: Invalid device tokens never accumulate: a token rejected by the provider is never
  sent to again.

## Assumptions

- Profile flags go on `GET /api/me/profile/` rather than a new endpoint: the app already reads
  the profile on login and on resume, and it already carries roles and permissions.
- Positions follow `POST /api/played/register/` (1-10), not the suggestion endpoint (1-4): a
  setlist for a special occasion needs the same room the played register has.
- The key follows `Played.tone` (1-3 characters, e.g. `G`, `A#`, `Bbm`), required on each item.
- Duplicate songs within a setlist are not rejected; the request did not ask for it.
- Any Sunday may be saved, past or future; there is no "too far ahead" limit.
- The push is sent after the save commits, inside the same request; with a congregation-sized
  worship ministry (tens of devices) a single synchronous send fits SC-002. The plan revisits
  this if it does not.
- A registered play for the date — any `Played` row — counts as confirmation, even if it does not
  match the setlist.
- The push payload is data-only; how the app renders it (notification, silent refresh) is the
  app's decision.
- `Profile.member` is set only in the Django admin (accounts spec); this feature does not add a
  way to link accounts to members.
- The reminder job and the server share the existing `./.env`, which gains the push credentials.
