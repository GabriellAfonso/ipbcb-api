# Feature Specification: Members Management for Church Leaders

**Feature Branch**: `010-members-management`

**Created**: 2026-09-25

**Status**: Draft

**Input**: User description: "Members management for church leaders (Android app screen).
Leaders (Profile.is_admin) can list, view, create, edit and delete church members, including a
leader-only member photo, with an edit history." (full request, including the decided
endpoints, history rules and security requirements, in the `/speckit-specify` invocation that
created this directory; the decisions it relies on are recorded in `specs/members/decisions.md`)

> **Access terms superseded by `specs/012-feature-role-permissions/`.** Below, "admin", "leader"
> and "church leaders" meant `Profile.is_admin` / `IsAdminUser`. Both are gone: access is now a
> role (Admin, Liderança, Mídia) with a level on a scope. The tables that named the old flag are
> updated; the narrative is kept as the record of this feature.

## Overview

The church keeps its membership roll in the `Member` table, but today it can only be edited
through the Django admin. The Android app reads it in two places, both limited to members and
both limited to valid profiles: the member list (id and name only) and the birthdays list.

This feature gives church leaders a screen in the app to manage the roll: list every member
record (valid or not), open one, create, edit, delete, attach a photo visible only to leaders,
and read who changed what and when.

Member data now includes religious affiliation tied to a named person, which is sensitive
personal data under LGPD art. 11. The feature therefore carries its own security requirements
(explicit response fields, member-free logs, private caching) and updates the constitution's
premise that the system holds no sensitive data.

**Domain spec**: `specs/members/spec.md` describes the whole members domain — what exists today
plus this feature.

**Scope**: backend only. The Android screen, including the delete confirmation dialog, lives in
the app repository.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Leader browses and opens member records (Priority: P1)

A leader opens the members screen and sees every member record, including records marked as
not valid, with name, photo, status and validity. The app filters the list on the phone. The
leader taps a member and sees the full record.

**Why this priority**: Every other story starts from the list and the record. Read access alone
already replaces asking whoever has Django admin access.

**Independent Test**: With members seeded (valid and not valid, with and without status), call
the list and detail as a leader and as a non-leader; the leader gets every record, the
non-leader is refused.

**Acceptance Scenarios**:

1. **Given** 3 valid and 1 not-valid member, **When** a leader requests the leader list,
   **Then** all 4 are returned, ordered by name, each with id, name, photo URL (or none),
   status (or none) and validity.
2. **Given** a member with status, role, two ministries, dates and a photo, **When** a leader
   requests that member, **Then** every field of the record is returned.
3. **Given** an authenticated member who is not a leader, **When** they request the leader list
   or a record, **Then** access is refused and no member data is returned.
4. **Given** no authentication, **When** anyone requests the leader list, **Then** it is refused
   as unauthenticated.
5. **Given** an id that matches no member, **When** a leader requests it, **Then** a not-found
   error is returned.
6. **Given** the leader list or a record was already fetched, **When** the leader fetches it
   again with nothing changed, **Then** the response tells the app its copy is still current,
   and no shared cache may store it.

---

### User Story 2 - Leader creates and edits a member (Priority: P1)

A leader adds a new member to the roll, or corrects an existing one: names, birth date, gender,
status, role, ministries, baptism date, validity. The picker options (statuses, roles,
ministries) come from the server.

**Why this priority**: Keeping the roll current is the purpose of the screen.

**Independent Test**: Fetch the picker options, create a member using them, edit some fields,
and read the record back.

**Acceptance Scenarios**:

1. **Given** statuses, roles and ministries exist, **When** a leader requests the picker
   options, **Then** all three lists are returned, each item with id and name, ordered by name.
2. **Given** a valid body with a name, **When** a leader creates a member, **Then** the member is
   stored, the full record is returned, and it appears in the leader list.
3. **Given** a body without a name, or with an unknown status/role/ministry id, an invalid
   gender, or a future date, **When** a leader creates a member, **Then** it is rejected with a
   validation error naming the offending value, and nothing is stored.
4. **Given** an existing member, **When** a leader sends only some fields, **Then** only those
   fields change and the others keep their values.
5. **Given** an existing member, **When** a leader sends a ministries list, **Then** the member's
   ministries become exactly that list.
6. **Given** an existing member, **When** a leader clears status or role, **Then** the field is
   stored as empty.
7. **Given** a member marked not valid, **When** a leader marks it valid again, **Then** it shows
   up again in the regular member list and birthdays.

---

### User Story 3 - Leader reads the edit history (Priority: P2)

A leader opens a member's history and reads, newest first, lines like "Ana changed status from
Não comungante to Comungante on 2026-09-25 14:02".

**Why this priority**: Several leaders edit the same roll; the history answers "who changed
this" without a separate audit system. Editing works without it, so it follows P1.

**Independent Test**: Create a member, edit two fields in one request, change ministries, and
read the history.

**Acceptance Scenarios**:

1. **Given** a leader created a member, **When** the history is read, **Then** it holds one
   creation entry with that leader as editor.
2. **Given** a leader changes status and birth date in one edit, **When** the history is read,
   **Then** there are two entries, one per field, each with the old value, the new value, the
   editor and the time.
3. **Given** a member in ministries A and B, **When** a leader sets ministries to A and C,
   **Then** there is one entry for ministries with old value "A, B" and new value "A, C".
4. **Given** an edit that sends fields with their current values, **When** it is saved,
   **Then** no history entry is written for them.
5. **Given** an edit is rejected by validation, **When** the history is read, **Then** nothing
   from that edit appears.
6. **Given** a leader reads a member's record or history, **When** the history is read again,
   **Then** no entry exists for the reads.

---

### User Story 4 - Leader manages the member photo (Priority: P2)

A leader uploads, replaces or removes a member's photo. Only leaders can see it.

**Why this priority**: Helps leaders recognise members, but the roll is usable without it.

**Independent Test**: Upload a photo, fetch its URL as a leader and as a plain member, replace
it, remove it, and check storage and history after each step.

**Acceptance Scenarios**:

1. **Given** a member without a photo, **When** a leader uploads a valid image, **Then** the
   record returns a photo URL, the file name contains no part of the member's name, and the
   history gains a "photo changed" entry with no file paths in it.
2. **Given** a member with a photo, **When** a leader uploads a new one, **Then** the record
   points at the new file and the old file is gone from storage.
3. **Given** a member with a photo, **When** a leader removes it, **Then** the record has no
   photo, the file is gone from storage, and the history gains a "photo removed" entry.
4. **Given** a file that is not a decodable image in an allowed format, or is over the size
   limit, **When** a leader uploads it, **Then** it is rejected and the current photo is intact.
5. **Given** a member photo URL, **When** a non-leader (member or not) requests it, **Then**
   access is refused.
6. **Given** a member without a photo, **When** a leader removes the photo, **Then** the request
   succeeds and no history entry is written.

---

### User Story 5 - Leader deletes a member (Priority: P3)

A leader deletes a member record — for example, a duplicate or a record created by mistake.
The app asks for confirmation by having the leader type the member's name; the server applies
the delete as requested.

**Why this priority**: Rare. Marking a record not valid covers most removals.

**Independent Test**: Create a member with a photo and history, delete it, and check record,
history and file are all gone.

**Acceptance Scenarios**:

1. **Given** a member with a photo and history, **When** a leader deletes it, **Then** the
   record, all its history and its photo file are removed.
2. **Given** an id that matches no member, **When** a leader deletes it, **Then** a not-found
   error is returned.

---

### Existing behaviour that must not change

- The regular member list keeps returning only id and name, only for valid profiles, only to
  members.
- The birthdays list keeps returning only valid profiles, only to members.

### Edge Cases

- **Storage fails after the database write of a delete or photo change**: the database change
  stands; the old file may remain on disk as an orphan. Never the reverse: a file is removed
  only after the database change is committed, so a failed save never loses the current photo.
- **Database write fails after the new photo file was stored**: the new file is removed and
  the member keeps the old photo and its file.
- **Two leaders edit the same member at the same time**: the last write wins; each edit
  writes history for the fields it changed against the values it replaced.
- **The editing leader's account is later deleted**: their history entries remain, with the
  editor shown as unknown.
- **A status, role or ministry is renamed or deleted through the Django admin**: history keeps
  the name as it was at edit time. Deleting one empties it on members without a history entry
  (changes made outside this screen are not tracked).
- **A leader loses leader status**: their next request is refused, including photo URLs they
  had already loaded, since each image request is checked again.
- **Body that is not a JSON object, or ids that are not integers**: rejected as a validation
  error, never a server error.
- **Edit changes birth date so baptism would come before birth**: rejected.

## Requirements *(mandatory)*

### Functional Requirements

**Access**

- **FR-001**: Every leader operation MUST require an authenticated caller who is a leader.
  Leader means `Profile.is_admin` for now, checked by the existing `IsAdminUser` permission
  class. No leader-named class is added (this supersedes `decisions.md` §1): if a separate
  leader role ever exists, every `IsAdminUser` use is reviewed then.
- **FR-002**: Non-leaders MUST receive a permission-denied error; unauthenticated callers an
  authentication error. Neither response carries member data.
- **FR-003**: Leader operations live under `/api/admin/members/`, separate from the regular
  `/api/members/`, which is unchanged.

**Listing and reading**

- **FR-004**: The leader list MUST return every member regardless of validity, without
  pagination or search, ordered by name, each item with exactly: id, name, photo URL (or
  none), status (id and name, or none), validity.
- **FR-005**: The member record MUST return exactly: id, name, first name, last name, birth
  date, gender, status, role, ministries (each id and name), baptism date, validity, photo URL,
  creation time.
- **FR-006**: The picker options MUST return all statuses, roles and ministries, each with id
  and name, ordered by name.
- **FR-007**: List, record, history and options responses MUST be private and non-storable by
  shared caches, and MUST let the app revalidate a copy it already has.

**Creating and editing**

- **FR-008**: A leader MUST be able to create a member. Name is required (non-blank, at most
  255 characters); every other field is optional. Validity defaults to valid.
- **FR-009**: A leader MUST be able to edit a member partially: only the fields sent change.
  Editable fields: name, first name, last name, birth date, gender, status, role, ministries,
  baptism date, validity. Creation time and photo are not editable this way.
- **FR-010**: Validation MUST reject, with a message naming the offending value and the expected
  shape: blank name; unknown status, role or ministry id; gender other than `M`/`F`; birth or
  baptism date in the future; baptism date before birth date (checked against the record as it
  would be after the edit).
- **FR-011**: A ministries value replaces the member's whole ministries list.
- **FR-012**: A rejected create or edit MUST store nothing, history included.

**Edit history**

- **FR-013**: Every change a leader makes through this feature MUST write history in the same
  all-or-nothing unit as the change itself. History is written by the application flow that
  makes the change, never by a side mechanism that does not know the editor.
- **FR-014**: Each history entry records: editor, member, field, old value, new value, time.
- **FR-015**: An edit MUST write one entry per field whose value actually changed, and none for
  fields sent unchanged.
- **FR-016**: Values MUST be stored as readable text so an entry reads "X changed F from A to
  B": status, role and ministries by name (as of edit time), dates as `YYYY-MM-DD`, validity as
  `true`/`false`, gender as its code, an empty value as none. Ministries: one entry per edit,
  names sorted and joined by ", ".
- **FR-017**: Creating a member MUST write one entry with field `created` and no values.
- **FR-018**: Uploading or replacing a photo MUST write one entry with field `photo` and the
  marker "photo changed"; removing it, the marker "photo removed". File paths never appear in
  history.
- **FR-019**: A leader MUST be able to read a member's history, newest first, each entry with
  editor (id and display name, or none if the account no longer exists), field, old value, new
  value and time.
- **FR-020**: Reads of member data MUST NOT be recorded.

**Photo**

- **FR-021**: A leader MUST be able to upload or replace a member's photo. The upload MUST go
  through the same content-based image validation as profile photos (decoded image, JPEG/PNG/
  WEBP/GIF, 10 MB limit), with the stored extension taken from the decoded format.
- **FR-022**: The photo MUST be stored as `members/<random>.<ext>` — no part of the member's
  name or id in the path — and MUST be separate from any user's profile photo (never shared or
  copied between the two).
- **FR-023**: Only leaders MUST be able to read member photos. This is enforced by the existing
  media access rule for the `members/` folder (spec 009); this feature adds no new media rule.
- **FR-024**: A leader MUST be able to remove a member's photo. Removing when there is none
  succeeds and writes nothing.
- **FR-025**: The previous photo file MUST be removed from storage on replace, on remove and
  on member delete, and only after the database change is committed.

**Deleting**

- **FR-026**: A leader MUST be able to delete a member. The delete removes the record, all its
  history (no anonymisation) and its photo file. No extra server-side confirmation, no soft
  delete, no recycle bin; confirmation is the app's job.

**Data protection**

- **FR-027**: Every response lists its fields explicitly; no response exposes "all fields" of
  a stored record.
- **FR-028**: Structured logs for these operations MUST carry the member id and never member
  data (names, dates, gender, status, role, ministries, photo paths).
- **FR-029**: The constitution MUST state that the members domain holds sensitive personal data
  (LGPD art. 11), while the public API schema stays an accepted risk because it describes
  shapes, not data.

**Existing behaviour**

- **FR-030**: The member model MUST carry a comment stating that `is_active` means "valid
  profile". The field keeps its name.
- **FR-031**: The regular member list and the birthdays list MUST keep returning only valid
  profiles. Status is what says whether a member is communicant; no new field is added for it.

### Key Entities

- **Member**: a person on the church roll. Name, optional first/last name, birth date, gender,
  status, role, ministries, baptism date, validity ("valid profile"), creation time, and now an
  optional leader-only photo.
- **Member status**: whether a member is communicant or not (and similar roll states). Managed
  in the Django admin.
- **Role**: a member's office in the church. Managed in the Django admin.
- **Ministry**: a church ministry; a member can be in several. Managed in the Django admin.
- **Member change log entry**: one change to one field of one member, by one editor, at one
  time, with old and new value as text. Belongs to the member and disappears with it; survives
  the editor's account being deleted.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A leader can find a member in the app and open the record without contacting
  anyone with Django admin access.
- **SC-002**: For a roll of 1,000 members, the leader list loads in one request, within 2
  seconds on a typical mobile connection.
- **SC-003**: 100% of leader-made changes (create, field edit, photo change or removal) appear
  in the member's history with editor, time, and old and new value; 0 reads appear.
- **SC-004**: 0 member photos or member records can be read by a non-leader, verified against
  every leader operation and the photo URL.
- **SC-005**: After a replace, remove or delete, 0 old photo files remain in storage, and a
  failed save leaves 0 members without their previous photo.
- **SC-006**: 0 log lines produced by these operations contain member names or other member
  fields.
- **SC-007**: The regular member list and birthdays return exactly what they returned before
  this feature for the same data.

## Assumptions

- Leader = `Profile.is_admin`; a separate leader role is out of scope.
- **Decided here (the request left it to the spec):** creation writes one `created` history
  entry with the creating leader and no values. `Member` has no "created by" column, so the
  history is the only place that answer can live; the values are the record itself.
- **Decided here:** date sanity rules (no future birth/baptism date, no baptism before birth)
  apply only to writes through this feature; existing rows that break them are not touched
  until someone edits them.
- **Decided here:** the history editor reference survives the editor's account deletion (shown
  as unknown) instead of taking the member's history with it.
- The roll is small (hundreds of members), so the full list without pagination fits one
  response; the app filters locally.
- Statuses, roles and ministries are managed in the Django admin; this feature only reads them
  for the pickers.
- The history needs no pagination: edits per member are few.
- Concurrent edits are rare; last write wins, no conflict detection.
- The existing error shape (`{"error_code", "detail"}`) and error codes are reused: validation
  errors, permission denied, not found.
- Photo URLs are the regular media URLs (`/ipbcb/media/members/...`), served through the access
  check from spec 009, which already restricts `members/` to leaders.
- Out of scope: contact, address and family fields; ecclesiastical dates other than baptism;
  auditing reads; a leader role separate from `is_admin`; changes to the regular member list
  and birthdays.

## Dependencies

- Spec 009 (protected media access) is deployed, with the `members/` folder rule restricted to
  leaders.
- The Android app implements the screen, including the delete confirmation that makes the
  leader type the member's name and warns that history and photo are deleted too.
