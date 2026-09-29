# Feature Specification: Member Tags in Gallery Photos

**Feature Branch**: `015-gallery-member-tags`

**Created**: 2026-09-29

**Status**: Draft

**Input**: User description: "Add member tags to gallery photos, so people can be marked in a
photo and the app can filter photos by who is in them. Also link a user's profile to their member
record, which the app needs to offer 'photos of me'." (full request — current state, profile
link, tags, endpoints, change feed, permissions, observability and out-of-scope list — in the
`/speckit-specify` invocation that created this spec.)

## Context

After features 013 and 014 the gallery can be built, pruned and synced from the app, but a photo
knows nothing about the people in it. A member looking for the photos they appear in has to
scroll the whole gallery, and the app cannot offer "photos of me", because the backend does not
know which member record belongs to the logged-in user either.

This feature adds **tags**: a manager marks which members appear in a photo, every member sees
who is in it, and the photo lists can be filtered by the people tagged. It also adds a hand-set
**link from a profile to its member record**, so the app can filter the gallery by the user's own
member id.

Feature 3 of 3 of the gallery work (013 write API, 014 trash and change feed).

### Relation to other specs

- **`specs/gallery/spec.md`** — the domain spec; gains tags, the filter, the two member lists and
  the feed rule for tags (FR-040).
- **`specs/accounts/spec.md`** — `Profile` gains the member link and the profile resource gains
  `member_id` (FR-041).
- **`specs/members/spec.md`** — a member can now be tagged in photos and linked to a profile;
  deleting a member removes both; renaming one changes photos in the feed (FR-042).
- **`specs/014-gallery-trash-sync/`** — its change feed rule (FR-034 there: every change to the
  resource counts, derived fields included) now covers the `members` field (FR-025 to FR-028).
- **`specs/012-feature-role-permissions/`** — amended (FR-043): the tagging endpoints join the
  `gallery` classification, and User Story 3 gains one narrow exception for the picker.
- **`specs/002-structured-json-logging/`** — tag changes are logged in its format.
- **`specs/001-api-error-handling/`** — every refusal uses its canonical error shape.

## Clarifications

### Session 2026-09-29

- Q: The same member id in both `add_member_ids` and `remove_member_ids` of a bulk request? →
  A: refuse the whole request with `400` naming the ids; neither list wins (FR-018).
- Q: How many photos per bulk request? → A: 200, one constant (FR-017).
- Q: Tags in the Django admin? → A: read-only on the photo page; tags are written only through
  the API, so the feed and the log see every change (FR-029).
- Q (planning): How are unknown and trashed photos reported by a failed tag write? → A: one
  `404` `NOT_FOUND` with `missing_photo_ids` (unknown and trashed merged, as 014 merges them into
  an order request's `unexpected`) and `missing_member_ids`, so a caller with `manage` does not
  learn what is in the trash (FR-015).
- Q (planning): How does the feed see a rename or deletion made in the Django admin? → A: gallery
  signal handlers on `Member`, connected by name without importing the members feature; the
  members spec's "No signals" rule concerns its history, which needs the editor (FR-026).

## Definitions

### Tag

A **tag** says that one member appears in one photo. A photo may carry any number of tags, a
member may be tagged in any number of photos, and a pair is tagged at most once. Only people who
exist as member records can be tagged.

A tag belongs to its photo: while the photo is in the trash (014) its tags are kept but invisible,
exactly as the photo is; they come back with it on restore and are removed when it is purged.

### Profile link

The **profile link** ties a user's profile to at most one member record, and a member record to
at most one profile. It is set by hand in the Django admin and is independent of the profile's
`is_member` flag.

### Endpoints

| Method | Route | Permission | Purpose |
|--------|-------|------------|---------|
| PUT    | `/api/photos/{id}/members/` | `manage` on `gallery` (method default) | replace the full set of tags of one photo |
| POST   | `/api/photos/members/` | `manage` on `gallery` (method default) | add and remove tags on many photos at once |
| GET    | `/api/gallery/taggable-members/` | `manage` on `gallery` (override, above `view`) | the tag picker: every member, `id` and `name` only |
| GET    | `/api/gallery/tagged-members/` | member (`IsMemberUser`) | the filter list: members tagged in at least one live photo |
| GET    | `/api/photos/?member_id=…` | member (unchanged) | photos in which **every** listed member is tagged |
| GET    | `/api/albums/{id}/photos/?member_id=…` | member (unchanged) | same filter, photos directly in the album |

Every endpoint of 013 and 014 is unchanged in route and permission.

### Request bodies

```json
PUT /api/photos/{id}/members/
{ "member_ids": [12, 40] }
```

```json
POST /api/photos/members/
{ "photo_ids": [301, 302], "add_member_ids": [12], "remove_member_ids": [40] }
```

### Member reference

`{"id": 12, "name": "Maria Souza"}` — the member's id and display name (`Member.name`), nothing
else. It is the only shape in which member data leaves the gallery endpoints.

### Photo resource

Keeps every field of 013 and 014 and gains one, last: `members`, a list of Member references for
the photo's tags, ordered by name, then id; `[]` for an untagged photo. Everywhere the Photo
resource is returned — the list endpoints, the 013 write responses, the 014 restore response, the
change feed, and the answers of the two tagging endpoints.

### Tagged member resource

`{"id": 12, "name": "Maria Souza", "photo_count": 17}` — `photo_count` is the number of **live**
photos the member is tagged in.

### Profile resource

Keeps every field (`name`, `is_member`, `photo_url`, `roles`, `permissions`) and gains
`member_id`: the linked member's id, or `null` when the profile is not linked. Read-only.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Tag the people in a photo (Priority: P1)

Someone on the media team opens a photo from last Sunday, picks from the list of members the
three people in it, and saves. From then on every member who opens the photo sees who is in it.

**Why this priority**: Tags are the base of everything else in this feature; the filter and
"photos of me" have nothing to work on without them.

**Independent Test**: As Mídia, read the picker, tag a photo with two members, read the photo as
a regular member (it lists both, by name), replace the tags with one other member (only that one
is listed).

**Acceptance Scenarios**:

1. **Given** a Mídia user, **When** they read `GET /api/gallery/taggable-members/`, **Then** they
   receive every member record, active or not, each with `id` and `name` only, ordered by name.
2. **Given** a live photo and a Mídia user, **When** they send `PUT /api/photos/{id}/members/`
   with two member ids, **Then** the answer is `200` with the Photo resource, whose `members`
   lists both members by name.
3. **Given** that photo, **When** a member without any role reads `GET /api/photos/` or
   `GET /api/albums/{album_id}/photos/`, **Then** the photo carries the same `members` list.
4. **Given** a tagged photo, **When** the full set is replaced with a different list, **Then**
   exactly that list is tagged afterwards: new ids are added, missing ones are removed, repeated
   ones kept.
5. **Given** a tagged photo, **When** the set is replaced with `[]`, **Then** the photo has no
   tags.
6. **Given** a request whose list names a member id twice, **When** it is sent, **Then** the
   duplicate is ignored and the answer is the same as with one occurrence.
7. **Given** an inactive member (`is_active` false), **When** they are tagged, **Then** it
   succeeds, and the tag stays listed for readers.
8. **Given** a member without any role, **When** they send the tag write or read the picker,
   **Then** the answer is `403`, whether or not the photo exists.

---

### User Story 2 - Find the photos someone is in (Priority: P1)

A member opens the gallery's filter, sees the list of people who appear in photos, with how many
photos each, and picks two of them. The gallery shows only the photos in which both appear.

**Why this priority**: The filter is what makes the tags useful to the congregation, and it is
what the app builds "photos of me" on.

**Independent Test**: Tag photo P1 with A and B, P2 with A, P3 with B; filter by A (P1, P2), by
A and B (P1 only), by an unknown id (empty), by `abc` (`400`).

**Acceptance Scenarios**:

1. **Given** tagged photos, **When** a member reads `GET /api/gallery/tagged-members/`, **Then**
   they receive every member tagged in at least one live photo, with `id`, `name` and the number
   of live photos they are tagged in, ordered by name.
2. **Given** P1 tagged with A and B, P2 with A only, **When** a member reads
   `GET /api/photos/?member_id=A&member_id=B`, **Then** the answer holds P1 only.
   *(Regression: AND, not OR.)*
3. **Given** the same photos, **When** the filter is `?member_id=A`, **Then** the answer holds P1
   and P2, in the list's usual order.
4. **Given** an album holding P1 and a sub-album holding P2, both tagged with A, **When** a
   member reads `GET /api/albums/{album}/photos/?member_id=A`, **Then** the answer holds P1 only.
5. **Given** a `member_id` that matches no member, **When** it is used, **Then** the answer is
   `200` with an empty list.
6. **Given** a `member_id` that is not an integer, **When** it is used, **Then** the answer is
   `400` naming the value.
7. **Given** a tagged photo moved to the trash, **When** a member filters by its member or reads
   the tagged-member list, **Then** the photo is not returned and is not counted.
   *(Regression: tags are hidden with a trashed photo.)*
8. **Given** a trashed photo that is restored, **When** a member reads it, **Then** its tags are
   back, unchanged.
9. **Given** a user who is not a member, **When** they read the tagged-member list, **Then** the
   answer is `403`.

---

### User Story 3 - Photos of me (Priority: P2)

A member opens "photos of me" in the app. The app reads the member id from the user's profile and
filters the gallery by it. A user whose profile is not linked yet sees no such shortcut.

**Why this priority**: It is the most wanted use of the tags, but it only needs one field on the
profile; the shortcut itself is the app's work.

**Independent Test**: In the Django admin, link a user's profile to member A; read the profile as
that user (`member_id` = A); try to link a second profile to A (refused); delete A (the profile's
`member_id` becomes `null`).

**Acceptance Scenarios**:

1. **Given** a profile that was never linked, **When** its user reads `GET /api/me/profile/`,
   **Then** `member_id` is `null` and every other field is as before.
2. **Given** a profile linked to member A in the Django admin, **When** its user reads the
   profile, **Then** `member_id` is A's id.
3. **Given** member A already linked to one profile, **When** an administrator links a second
   profile to A in the Django admin, **Then** the form shows a validation error and nothing is
   saved.
4. **Given** the Django admin profile form, **When** an administrator picks the member, **Then**
   they can search members by name instead of scrolling a list of every member.
5. **Given** a linked profile, **When** the user sends `PATCH /api/me/profile/` with a
   `member_id`, **Then** the link does not change.
6. **Given** a linked member that is deleted, **When** the user reads the profile, **Then**
   `member_id` is `null`, and the profile and its user still exist.
7. **Given** a profile flagged `is_member` false linked to a member, or one flagged true without
   a link, **When** anything is read, **Then** `is_member` and the link keep their own values;
   neither changes the other.

---

### User Story 4 - Tag many photos at once (Priority: P2)

After a baptism the media team selects the thirty photos of the ceremony and tags the person
baptized in all of them in one action, without touching anyone else tagged in those photos. Later
they notice a wrong tag on twelve of them and remove it the same way.

**Why this priority**: Tagging one photo at a time works, but an event produces dozens of photos
of the same people.

**Independent Test**: Tag P1 with A and B, P2 with B; send a bulk request adding C to P1 and P2
and removing B from both; P1 holds A and C, P2 holds C.

**Acceptance Scenarios**:

1. **Given** P1 tagged with A and B and P2 with B, **When** a manager sends
   `POST /api/photos/members/` with `photo_ids` P1, P2, `add_member_ids` C and
   `remove_member_ids` B, **Then** P1 is tagged A and C, P2 is tagged C, and the answer is `200`
   with both Photo resources. *(Regression: other tags are kept.)*
2. **Given** a pair that is already tagged, **When** it is added, **Then** nothing changes for
   it; **given** a pair that is not tagged, **When** it is removed, **Then** nothing changes for
   it; neither is an error.
3. **Given** a bulk request naming one unknown photo id, one trashed photo id or one unknown
   member id, **When** it is sent, **Then** the answer is an error naming every offending id, and
   no tag of any photo in the request changed. *(Regression: atomic failure.)*
4. **Given** a bulk request with more photos than the limit, **When** it is sent, **Then** the
   answer is `400` naming the count and the limit, and nothing changes.
5. **Given** the same member id in both `add_member_ids` and `remove_member_ids`, **When** the
   request is sent, **Then** the answer is `400` (`VALIDATION_ERROR`) naming those ids, and
   nothing changes.

---

### User Story 5 - The app's copy follows the tags (Priority: P2)

The app keeps a copy of the gallery on the device and updates it from the change feed. When
someone is tagged or untagged, renamed, or removed from the roll, the photos affected show the
change after the next sync.

**Why this priority**: Without it the tags on the device go stale and the filter, which the app
applies to its local copy, gives wrong answers.

**Independent Test**: Read the feed for a cursor; tag a photo, rename a member tagged in another
photo, delete a member tagged in a third; read the feed with the cursor: the three photos come
back with their new `members`.

**Acceptance Scenarios**:

1. **Given** a cursor, **When** a photo's tags are replaced or changed by a bulk request, **Then**
   the next feed read returns every photo whose `members` changed, and no photo the request left
   unchanged.
2. **Given** a cursor, **When** a member tagged in photos P1 and P2 is renamed, **Then** the next
   feed read returns P1 and P2 with the new name. *(Regression.)*
3. **Given** a cursor, **When** a member tagged in photos P1 and P2 is deleted, **Then** the next
   feed read returns P1 and P2 without that member.
4. **Given** a rename or a deletion made in the Django admin rather than through the API, **When**
   the feed is read, **Then** the result is the same as in scenarios 2 and 3.
5. **Given** a cursor, **When** a member who is not tagged anywhere is renamed or deleted, or a
   tagged member changes a field other than `name`, **Then** no photo is returned for it.
6. **Given** an app version released before this feature, **When** it reads any gallery list or
   the feed, **Then** every field it read before is still there, with the same meaning; only
   `members` is added.

---

### User Story 6 - The media team sees names, never the roll (Priority: P3)

The picker gives the media team the names they need to tag photos, and nothing else of the
membership roll.

**Why this priority**: It is a guard on User Story 1 rather than a feature of its own, but it is
the one place this feature touches the separation that spec 012 exists to keep.

**Independent Test**: As Mídia, read the picker (names and ids only) and `GET /api/members/`,
`GET /api/admin/members/` and a `members/` file (all refused as before).

**Acceptance Scenarios**:

1. **Given** a Mídia user, **When** they read the picker, **Then** each entry carries exactly
   `id` and `name`: no status, role, ministries, birth date, gender, activity flag or photo.
   *(Regression.)*
2. **Given** a Mídia user who is not flagged a member, **When** they read `GET /api/members/`,
   **Then** the answer is `403`, as before this feature. *(Regression.)*
3. **Given** a Mídia user, **When** they call any `api/admin/members/` endpoint or request a
   `members/` file, **Then** the answer is `403`, as before.
4. **Given** any reader of the gallery, **When** they read a Photo resource or the tagged-member
   list, **Then** the only member data they receive is the Member reference (and `photo_count`).

---

### Edge Cases

- **Write on a trashed photo.** `PUT …/members/` on a trashed photo is `404`, like every 013
  write that names a trashed item (014 FR-007); in the bulk request a trashed id is an offending
  id, and the whole request fails.
- **Member deleted while tagged.** Its tags are removed with it, on every path (API and Django
  admin), and each live photo it was tagged in counts as changed in the feed. A trashed photo it
  was tagged in simply comes back without the tag if restored.
- **Photo purged.** Its tags are removed with its row; the feed already reports the photo as
  deleted (014).
- **Member renamed while their photo is in the trash.** Nothing is reported while the photo is
  trashed; its restore reports it as changed (014 FR-020), with the current name.
- **Inactive member.** `is_active` plays no part in tags: inactive members are in the picker, can
  be tagged, keep their tags, are listed on photos and in the tagged-member list, and can be used
  in the filter.
- **Tagged-member list and trash.** A member whose only tagged photos are all trashed is not in
  the list; `photo_count` never counts a trashed photo.
- **Filter with a repeated id.** `?member_id=A&member_id=A` is the same as `?member_id=A`.
- **Filter mixing valid and invalid values.** Any value that is not an integer makes the whole
  request `400`, even if the others are valid.
- **Filter and the feed.** The change feed has no member filter; the app filters its local copy
  by the `members` of each photo.
- **Tag write with an empty body list.** `PUT` with `member_ids: []` clears the photo's tags. A
  bulk request with no photo, or with neither members to add nor to remove, is `400`.
- **Concurrent tag writes on the same photo.** Each request is applied as a whole; the result is
  the state of one of them, never a mix, and the feed reports the final state.
- **Concurrent member deletion and tag write.** A tag write that names a member deleted in the
  meantime fails as an unknown member; it never leaves a tag pointing at nothing.
- **Profile of a deleted user.** The link goes with the profile; the member record is untouched
  and can be linked to another profile.
- **Same person, two accounts.** Only one profile can hold the link; the other account stays
  unlinked. Which one is the administrator's choice.
- **Member name changed in the Django admin.** Same effect on the feed as through the API
  (User Story 5, scenario 4); the members spec already records that admin edits bypass the
  history, which does not change here.

## Requirements *(mandatory)*

### Functional Requirements

**Profile link**

- **FR-001**: A profile MUST be linkable to at most one member record, and a member record to at
  most one profile. Existing profiles start unlinked.
- **FR-002**: The link MUST be set and changed only in the Django admin, whose profile form offers
  a search over members by name. Linking a member that already has a profile MUST be refused with
  a validation error on the form, and nothing saved.
- **FR-003**: No API endpoint may create, change or remove the link; `PATCH /api/me/profile/`
  MUST ignore or refuse a `member_id`, as it does the other read-only fields today. No link is
  ever made automatically, by name or otherwise.
- **FR-004**: Deleting a member MUST leave the linked profile and its user in place, unlinked.
- **FR-005**: `is_member` MUST stay independent of the link: neither sets, clears nor checks the
  other.
- **FR-006**: The profile resource MUST gain `member_id` (the linked member's id, or `null`),
  read-only. Every existing field keeps its value and meaning.

**Tags**

- **FR-007**: A tag MUST pair one photo and one member record, at most once per pair. Only
  existing member records can be tagged; there is no free-text tag.
- **FR-008**: `Member.is_active` MUST NOT affect tagging, the picker, the tags shown on a photo,
  the tagged-member list or the filter.
- **FR-009**: Deleting a member MUST remove their tags. Purging a photo (014) MUST remove its
  tags. Trashing a photo MUST keep its tags, and restoring it MUST bring them back unchanged.
- **FR-010**: Each tag MUST record who created it and when, for auditing. Neither is ever
  returned by any endpoint.
- **FR-011**: The Photo resource MUST gain `members`, the photo's tags as Member references,
  ordered by name then id; `[]` when untagged. It is added on every endpoint that returns the
  resource. Nothing is removed from any existing response.
- **FR-012**: A trashed photo's tags MUST NOT be visible anywhere a trashed photo is not: in any
  list, the filter, the tagged-member list or its counts.

**Writing tags**

- **FR-013**: `PUT /api/photos/{id}/members/` MUST require `manage` on `gallery`, replace the
  photo's tags with exactly the given `member_ids`, and answer `200` with the Photo resource.
- **FR-014**: `POST /api/photos/members/` MUST require `manage` on `gallery`, add every pair of
  (`photo_ids` × `add_member_ids`) that is not tagged yet, remove every pair of
  (`photo_ids` × `remove_member_ids`) that is, change no other tag, and answer `200` with the
  Photo resources of the listed photos.
- **FR-015**: Both writes MUST be atomic: an unknown photo id, a trashed photo id or an unknown
  member id MUST fail the whole request with a domain error in the canonical shape (spec 001)
  whose body names every offending id by kind, and MUST leave every tag as it was. An unknown or
  trashed photo in the route of `PUT` is `404`, as in 013.
- **FR-016**: Repeated ids in any list MUST be ignored, not refused.
- **FR-017**: The bulk request MUST refuse, with `400` naming the count and the limit, more
  photos than one constant limit of **200** photos per request (counted after duplicates are
  dropped). It MUST also refuse an empty `photo_ids`, and a request in which both member lists
  are empty.
- **FR-018**: A member id present in both `add_member_ids` and `remove_member_ids` of one bulk
  request MUST fail the whole request with `400` (`VALIDATION_ERROR`) naming those ids; nothing
  changes. The system never guesses which list was meant.
- **FR-019**: A tag write MUST NOT change anything else on the photo, and adding a tag that
  exists or removing one that does not MUST NOT count as a change of that photo.

**Reading tags**

- **FR-020**: `GET /api/gallery/taggable-members/` MUST require `manage` on `gallery`, declared as
  an override above the `GET` default (spec 012), and return every member record, active or not,
  as Member references ordered by name then id. It MUST return no other member field.
- **FR-021**: `GET /api/gallery/tagged-members/` MUST require membership (`IsMemberUser`) and
  return every member tagged in at least one live photo, as Tagged member resources ordered by
  name then id.
- **FR-022**: `GET /api/photos/` and `GET /api/albums/{id}/photos/` MUST accept a repeatable
  `member_id` parameter. With one or more values, they return only the live photos tagged with
  **every** listed member, in the endpoint's usual order; the album endpoint still returns only
  photos directly in the album. Without it, both behave exactly as before.
- **FR-023**: A `member_id` value that is not an integer MUST be `400` (`VALIDATION_ERROR`)
  naming the value; an integer that matches no member MUST yield `200` with an empty list.
- **FR-024**: Reading tags and filtering MUST be open to every member and MUST NOT require any
  level on `members`.

**Change feed (amends 014)**

- **FR-025**: A photo MUST count as changed in the feed (014 FR-034) when tags are added to it or
  removed from it, by either write endpoint.
- **FR-026**: Every live photo in which a member is tagged MUST count as changed when that
  member's `name` changes, and when that member is deleted, whatever the path of the change: the
  members management API or the Django admin.
- **FR-027**: A change to any other member field, or to a member tagged nowhere, MUST NOT make
  any photo count as changed.
- **FR-028**: No photo may be reported as changed by a tag write that did not change its tags
  (FR-019).

**Tags in the Django admin**

- **FR-029**: The Django admin photo page MUST show a photo's tags read-only; no admin page may
  add, change or remove a tag. Tags are written only through the two tag endpoints, so every
  change reaches the feed (FR-025) and the log (FR-036). Deleting a member in the Django admin
  still removes its tags (FR-009, FR-026).

**Permissions (amends spec 012)**

- **FR-030**: `PUT /api/photos/{id}/members/`, `POST /api/photos/members/` and
  `GET /api/gallery/taggable-members/` MUST require `manage` on scope `gallery`, reached by Admin,
  Liderança and Mídia. A caller without it gets `403` before existence is checked.
- **FR-031**: The picker is the one deliberate exception to spec 012 User Story 3: through it,
  the Mídia role reads the **names** of members, and nothing else about them. No other endpoint
  gives Mídia any member data, and Mídia keeps `403` on `GET /api/members/` (unless flagged a
  member, as today), on every `api/admin/members/` endpoint and on `members/` files.
- **FR-032**: `GET /api/members/` and the `members` scope MUST NOT change.

**Data protection**

- **FR-033**: Tags tie a named member to church photos, so the members domain's data-protection
  rules (constitution, Security) apply to them: every serializer that exposes member data lists
  its fields explicitly, and logs carry member ids, never member names.
- **FR-034**: The picker and the tagged-member list MUST NOT be storable by a shared cache in a
  way that hands member names to a caller who could not read them from the endpoint (the
  constitution's Caching rule; the members domain keeps its management responses private).
- **FR-035**: The only member data the gallery endpoints return is the Member reference and, in
  the tagged-member list, `photo_count`.

**Observability**

- **FR-036**: Each tag write that changes at least one tag MUST write one structured JSON log line
  (spec 002) with the photo ids, the member ids added and removed per photo, and the actor's id. A
  write that changes nothing logs nothing, or logs it as such; never member names.

**Specs**

- **FR-040**: `specs/gallery/spec.md` MUST describe tags, the two member lists, the filter, the
  `members` field and the feed rule, in the same commit as the code.
- **FR-041**: `specs/accounts/spec.md` MUST describe the profile link and `member_id`.
- **FR-042**: `specs/members/spec.md` MUST state that a member can be tagged in photos and linked
  to a profile, that deleting a member removes their tags and unlinks the profile, and that a
  rename or deletion changes the tagged photos in the gallery feed.
- **FR-043**: `specs/012-feature-role-permissions/spec.md` MUST list the three tagging endpoints
  in the `gallery` section of Endpoint Classification (the picker as an override), state that the
  tagged-member list and the filter are member endpoints outside the classification, and amend
  User Story 3 and the `gallery` matrix note with the exception of FR-031.

**Architecture and tests**

- **FR-044**: Tagging, the lists, the filter and the profile link MUST follow the project
  layering, with business rules outside the views, refusals as domain exceptions naming the
  offending values, and a regression test for each of: AND filtering with two members, bulk
  add/remove keeping other tags, atomic failure, tags hidden with a trashed photo, the picker
  exposing only `id` and `name`, Mídia reaching the picker but not `GET /api/members/`, and the
  feed reporting a renamed tagged member.
- **FR-045**: The schema changes MUST come from generated migrations, with no data migration:
  existing profiles start unlinked and existing photos untagged.

### Key Entities

- **Tag** (new): a photo, a member record, who created it and when. Unique per photo and member.
  Removed with its member or when its photo is purged; kept, invisible, while its photo is in the
  trash.
- **Profile** (existing, extended): gains an optional, unique link to a member record.
- **Member** (existing, unchanged in shape): can now be tagged and linked; its `name` is what the
  gallery shows.
- **Photo** (existing, unchanged in shape): gains its tags through the Tag entity; its resource
  gains `members`.
- **Member reference** (derived): a member's id and name, the only member shape the gallery
  returns.
- **Tagged member** (derived): a Member reference plus the number of live photos it is tagged in.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A member can reach every photo they are tagged in with one filter, and no photo they
  are not tagged in is returned by it.
- **SC-002**: The media team can tag one person in every photo of an event with a single action,
  for an event of up to the bulk limit.
- **SC-003**: After a tag change, a member rename or a member deletion, every affected photo shows
  the new state on a member's device at their next sync, and no unaffected photo is transferred
  for it.
- **SC-004**: A user holding only the Mídia role obtains 0 member fields other than id and name,
  from any endpoint.
- **SC-005**: 0 tags of trashed photos are visible to members, in any list, filter or count.
- **SC-006**: An app version released before this feature keeps loading the gallery and the
  profile with no change to what it reads.
- **SC-007**: A failed tag write leaves 0 tags changed.
- **SC-008**: Each regression listed in FR-044 is covered by an automated check.

## Assumptions

- **Status codes.** Both tag writes answer `200` with the Photo resources, so the app can update
  its screen without another read, like 013's `PATCH`.
- **Offending ids in one error.** An atomic failure names every offending id of the request in
  one answer, grouped by kind (photos, members), so the app can fix them all at once. A trashed
  photo is reported as a missing photo, as everywhere outside the trash (014).
- **Error status for the atomic failure.** `404`, as in 013 for unknown ids referenced in a body
  (`parent_id`, `album_id`), with the ids in the body (clarified).
- **Picker size.** The picker is not paginated or searchable server-side: the roll holds a few
  hundred records, and the app searches the list it holds, as with every gallery list.
- **Tagged-member list size.** Not paginated, for the same reason.
- **Names shown.** The Member reference carries `Member.name`, the display name already shown to
  members by `GET /api/members/`; `first_name` and `last_name` are never shown by the gallery.
- **Inactive members' names become visible to members through tags.** The request decided that a
  tag stays visible after its member becomes inactive; `GET /api/members/` still lists active
  members only. Accepted as a consequence of that decision.
- **Visitors with a member record.** A person on the roll with the `Visitante` status is a member
  record and can be tagged; people with no record cannot.
- **Tag writes and `updated_at`.** How a tag change, a member rename or a member deletion makes
  the photos appear in the feed is the plan's decision; the spec requires only that it covers the
  Django admin paths as well (FR-026).
- **Portuguese messages.** Refusals the management panel shows (unknown or trashed ids, bulk
  limit) are in Portuguese; the not-integer filter value addresses client developers and is in
  English, as the 013 order-mismatch message.

## Out of Scope

- Any Android app change, including the "photos of me" shortcut and the filter screen.
- Face detection or automatic tagging: tags are always set by a person.
- A member removing their own tag or asking to be untagged; a manager does it for now.
- Tagging people who are not member records.
- An OR filter ("photos with A or with B").
- An endpoint to link a profile to a member; deriving `is_member` from the link.
- Any change to `GET /api/members/` or to what the `members` scope exposes.
- A member filter on the change feed.
