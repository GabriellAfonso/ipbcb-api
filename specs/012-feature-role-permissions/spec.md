# Feature Specification: Feature-Scoped Permissions with Roles

**Feature Branch**: `012-feature-role-permissions`

**Created**: 2026-09-28

**Status**: Draft

**Input**: User description: "Feature-scoped permission system with roles for the Android app's
management panel. Replace the admin/member binary with per-feature permissions (scopes) with
levels, grouped into roles." (full request — current state, levels, HTTP-method mapping, roles,
scope matrix, accepted risks, protected media change, decided implementation, spec adjustments,
out-of-scope list and expected tests — in the `/speckit-specify` invocation that created this
spec.)

## Context

Today management access is a single yes/no: `Profile.is_admin`. Whoever has it can do everything
in every management area, including deleting data; whoever lacks it can do nothing. Two needs do
not fit that:

1. **Safety** — a tier below the administrator that can do everything *except* delete data.
2. **Separation** — granting access to one area without granting it to another (e.g. someone who
   manages the photo gallery must not see the membership roll, which holds sensitive personal
   data under LGPD art. 11).

This feature replaces the binary with **permissions per feature area (scope)**, each at a
**level**, bundled into **roles**. Church membership (`Profile.is_member`) is untouched: it
governs the common content of the app, not the management panel.

### Terminology change

Specs 009, 010 and `specs/members/spec.md` use "leader" / "church leaders" to mean
`Profile.is_admin`. From this feature on, **Leader (Liderança) is the name of one role**, and
`is_admin` no longer exists. Those specs are rewritten in terms of roles and scopes (FR-029).

## Definitions

### Levels

Hierarchical — each level includes the one above it.

| Level    | Grants                         |
|----------|--------------------------------|
| `view`   | read                           |
| `manage` | read, create, change           |
| `owner`  | everything, including delete   |

### Default level per request method

| Method                  | Required level |
|-------------------------|----------------|
| `GET`                   | `view`         |
| `POST`, `PUT`, `PATCH`  | `manage`       |
| `DELETE`                | `owner`        |

Any endpoint may declare a **higher** level than its method's default. This is a general rule,
not a one-off: many things will be editable by the administrator only. An endpoint cannot
declare a lower level than the default unless it names the method in `lowered=` and the
endpoint is listed below; an unlisted lower override still fails at import.

### Lowered overrides

Each entry is a deliberate exception to the method default, with its reason.

| Method | Endpoint | Scope | Level | Reason |
|--------|----------|-------|-------|--------|
| DELETE | `api/setlists/{date}/` | `songs` | `manage` | A setlist is transient: the plan for a single Sunday, useless once that service is over, and rebuilt in seconds. `owner` protects data that is costly or permanent to lose, which this is not, so deleting it is the same act as saving it (spec 017): whoever may save it (`manage` + worship member) may delete it. The lasting record of the Sunday is `Played`, which this never touches |

### Roles

| Role          | Display name (pt-BR) |
|---------------|----------------------|
| `Role.ADMIN`  | Admin                |
| `Role.LEADER` | Liderança            |
| `Role.MEDIA`  | Mídia                |

- There is **no** member role. Membership stays the `Profile.is_member` flag. Membership and
  roles are orthogonal: a role never requires membership, and membership never grants a role.
- A user may hold several roles; their permissions are the **union** (highest level per scope).
- The media role's identifier collides with the `features/media` feature, so code always refers
  to the role through the enumeration, never through the bare string.

### Scope matrix

| Scope                    | ADMIN | LEADER | MEDIA  |
|--------------------------|-------|--------|--------|
| `members`                | owner | manage | —      |
| `schedule`               | owner | manage | —      |
| `songs`                  | owner | manage | —      |
| `gallery`                | owner | owner  | owner  |
| `events`                 | owner | manage | manage |
| `notices`                | owner | manage | manage |
| `reports.hymnal_history` | owner | view   | view   |

"—" = no access at all to that scope's management endpoints, not even read.

- **ADMIN is owner of every scope, including scopes added later**, decided in code and never
  read from stored permissions. Adding a scope can therefore never lock the administrator out.
- **LEADER can do everything except delete**, in every scope but `gallery`. No `DELETE` is
  allowed to a leader outside `gallery`, member deletion included. On `gallery` Leader is `owner`
  (feature 013, below).
- **Reports are scopes of their own**, one per report (`reports.<name>`), so each report can be
  released to different roles. The hymnal history report is not sensitive and is readable by
  every role that reaches the panel. Writing its configuration requires `owner`.
- **`events` and `notices`** are future features. This feature only reserves their scopes and
  who will hold them; it creates no data or endpoints for them.
- **`gallery`**: write endpoints in `specs/013-gallery-write-api/`. Feature 013 raised LEADER
  and MEDIA from `manage` to `owner` on this scope (data migration
  `core/0006_gallery_owner_for_leader_media.py`), so the three roles can remove album covers and,
  in feature 014, delete albums and photos. This is the one scope where LEADER deletes.
  Feature 015 adds the tag picker here (`manage`), through which MEDIA reads the **names** of
  members — the one deliberate exception to "MEDIA sees nothing of the roll" (User Story 3).

## Endpoint Classification

Every endpoint that required `is_admin` before this feature, by scope and required level.
"Default" means the level comes from the method; "override" means a higher level is declared.

### members

| Method | Endpoint                               | Scope     | Level  | Why                                 |
|--------|----------------------------------------|-----------|--------|-------------------------------------|
| GET    | `api/admin/members/`                   | `members` | view   | default                             |
| POST   | `api/admin/members/`                   | `members` | manage | default                             |
| GET    | `api/admin/members/{id}/`              | `members` | view   | default                             |
| PATCH  | `api/admin/members/{id}/`              | `members` | manage | default — includes status changes   |
| DELETE | `api/admin/members/{id}/`              | `members` | owner  | default                             |
| GET    | `api/admin/members/options/`           | `members` | view   | default                             |
| PUT    | `api/admin/members/{id}/photo/`        | `members` | manage | default — upload or replace         |
| DELETE | `api/admin/members/{id}/photo/`        | `members` | owner  | default — a leader can replace a photo but not remove it |
| GET    | `api/admin/members/{id}/history/`      | `members` | view   | default                             |

### schedule

| Method | Endpoint                  | Scope      | Level  | Why                                               |
|--------|---------------------------|------------|--------|---------------------------------------------------|
| POST   | `api/schedule/generate/`  | `schedule` | manage | default — persists nothing, but it is a POST and exists only to feed a save |
| POST   | `api/schedule/save/`      | `schedule` | manage | default — overwrites the whole month (accepted risk) |

`GET api/schedule/current/` stays a member endpoint (`is_member`) and is not part of this
classification.

`GET api/members/` (the member list) is a member endpoint that the schedule screen also
needs, to pick whom to roster. It accepts a member **or** `view` on `schedule` (FR-031), so a
Liderança or Admin who is not flagged as a member can still build the schedule. Mídia, without
`schedule`, still needs membership.

### songs

| Method | Endpoint                     | Scope   | Level  | Why                                      |
|--------|------------------------------|---------|--------|------------------------------------------|
| POST   | `api/played/register/`       | `songs` | manage | default — creates or replaces a Sunday's plays (accepted risk) |
| POST   | `api/chord-charts/`          | `songs` | manage | default                                  |
| PATCH  | `api/chord-charts/{id}/`     | `songs` | manage | default                                  |
| POST   | `api/lyrics/`                | `songs` | manage | default                                  |
| PATCH  | `api/lyrics/{id}/`           | `songs` | manage | default                                  |

`GET api/chord-charts/` and `GET api/lyrics/` stay public, as today.

### reports.hymnal_history

| Method | Endpoint                                      | Scope                    | Level  | Why                       |
|--------|-----------------------------------------------|--------------------------|--------|---------------------------|
| GET    | `api/hymnal-history/occurrences/`             | `reports.hymnal_history` | view   | default — report read     |
| GET    | `api/hymnal-history/top-hymns/`               | `reports.hymnal_history` | view   | default — report read     |
| PATCH  | `api/hymnal-history/settings/`                | `reports.hymnal_history` | owner  | override — configuration  |
| POST   | `api/hymnal-history/service-windows/`         | `reports.hymnal_history` | owner  | override — configuration  |
| PATCH  | `api/hymnal-history/service-windows/{id}/`    | `reports.hymnal_history` | owner  | override — configuration  |
| DELETE | `api/hymnal-history/service-windows/{id}/`    | `reports.hymnal_history` | owner  | default                   |
| GET    | `api/hymnal-history/service-windows/`         | `reports.hymnal_history` | view   | default — Leader and Media see the windows that shape the report, read-only |
| GET    | `api/hymnal-history/service-windows/{id}/`    | `reports.hymnal_history` | view   | default — same as above   |

`GET api/hymnal-history/settings/` and `POST api/hymnal-history/events/` stay public, as today:
the app reads the settings and syncs events before anyone logs in.

### gallery

Added by features 013 (`specs/013-gallery-write-api/`), 014
(`specs/014-gallery-trash-sync/`) and 015 (`specs/015-gallery-member-tags/`). Admin, Liderança
and Mídia all hold `owner` here.

| Method | Endpoint                                     | Scope     | Level  | Why                          |
|--------|----------------------------------------------|-----------|--------|------------------------------|
| POST   | `api/albums/`                                | `gallery` | manage | default                      |
| PATCH  | `api/albums/{id}/`                           | `gallery` | manage | default                      |
| DELETE | `api/albums/{id}/`                           | `gallery` | owner  | default — to the trash       |
| PUT    | `api/albums/order/`                          | `gallery` | manage | default                      |
| PUT    | `api/albums/{id}/cover/`                     | `gallery` | manage | default                      |
| DELETE | `api/albums/{id}/cover/`                     | `gallery` | owner  | default                      |
| POST   | `api/photos/`                                | `gallery` | manage | default                      |
| PATCH  | `api/photos/{id}/`                           | `gallery` | manage | default                      |
| DELETE | `api/photos/{id}/`                           | `gallery` | owner  | default — to the trash       |
| PUT    | `api/albums/{id}/photos/order/`              | `gallery` | manage | default                      |
| GET    | `api/gallery/trash/`                         | `gallery` | owner  | override — shows who deleted and uploaded, and trashed files |
| POST   | `api/gallery/trash/albums/{id}/restore/`     | `gallery` | owner  | override — undoes a delete   |
| POST   | `api/gallery/trash/photos/{id}/restore/`     | `gallery` | owner  | override — undoes a delete   |
| PUT    | `api/photos/{id}/members/`                   | `gallery` | manage | default — replace a photo's tags |
| POST   | `api/photos/members/`                        | `gallery` | manage | default — bulk tag changes   |
| GET    | `api/gallery/taggable-members/`              | `gallery` | manage | override — names of every member for the tag picker; the Mídia exception of User Story 3 |

The gallery reads (`GET api/albums/`, `GET api/photos/`, `GET api/albums/{id}/photos/`, with or
without the `member_id` filter), the change feed (`GET api/gallery/changes/`) and the
tagged-member list (`GET api/gallery/tagged-members/`) are member endpoints (`is_member`), outside
this classification.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Administrator keeps full control (Priority: P1)

The people who hold `is_admin` today keep doing everything they do now, including deleting,
after the switch. The flag is converted, not lost.

**Why this priority**: Without it the deploy locks every current manager out of the panel.

**Independent Test**: Migrate a database with one `is_admin=True` and one `is_admin=False`
profile; the first can reach every management endpoint with every method, the second none.

**Acceptance Scenarios**:

1. **Given** a profile with `is_admin=True` before the migration, **When** the migration runs,
   **Then** the user holds the Admin role.
2. **Given** a profile with `is_admin=False`, **When** the migration runs, **Then** the user
   holds no role.
3. **Given** an administrator, **When** they call any endpoint of any scope with any method,
   **Then** it is allowed — including a scope for which no permission was ever stored.
4. **Given** an administrator, **When** they delete a member, **Then** it succeeds.
5. **Given** a freshly migrated database where nobody touched the Django admin, **When** the
   stored levels of the Leader and Media roles are read, **Then** they match the scope matrix
   exactly — no role is created empty.

---

### User Story 2 - Leader manages everything but cannot delete (Priority: P1)

A church leader manages members, the monthly schedule and songs, and reads the hymnal report.
Nothing they do outside the gallery can delete data (on `gallery` they are `owner` since
feature 013).

**Why this priority**: The safety tier is the main motivation of the feature.

**Independent Test**: As a user holding only the Leader role, call every classified endpoint;
reads and writes succeed, every `DELETE` and every configuration write is refused.

**Acceptance Scenarios**:

1. **Given** a leader, **When** they list, create, edit a member or change a member's roll
   status, **Then** it succeeds.
2. **Given** a leader, **When** they delete a member or a member photo, **Then** the answer is
   `403`.
3. **Given** a leader, **When** they save the month's schedule, register Sunday plays, or create
   or edit a chord chart or lyrics, **Then** it succeeds.
4. **Given** a leader, **When** they read the hymnal occurrences or ranking, **Then** it
   succeeds.
5. **Given** a leader, **When** they change the hymnal history settings or create, edit or
   delete a service window, **Then** the answer is `403`.
6. **Given** a leader, **When** they request a file under `members/`, **Then** it is served.

---

### User Story 3 - Media team is kept away from the roll (Priority: P2)

A person on the media team reaches the panel but sees nothing of the membership roll, except
the members' names in the gallery tag picker (scenario 5, feature 015).

**Why this priority**: Separation between areas is the second motivation, and the roll is the
only sensitive data in the system.

**Independent Test**: As a user holding only the Media role, call the member endpoints and a
`members/` file (all refused) and the hymnal report (allowed).

**Acceptance Scenarios**:

1. **Given** a media user, **When** they list members or read one, **Then** the answer is `403`.
2. **Given** a media user, **When** they request a file under `members/`, **Then** the answer is
   `403`.
3. **Given** a media user, **When** they call schedule or songs management endpoints, **Then**
   the answer is `403`.
4. **Given** a media user, **When** they read the hymnal occurrences or ranking, **Then** it
   succeeds.
5. **Given** a media user, **When** they read the gallery tag picker
   (`GET api/gallery/taggable-members/`, feature 015), **Then** it succeeds and returns each
   member's `id` and `name` and nothing else. This is the one deliberate exception to this story:
   the media team needs names to tag photos. Every other member endpoint and every `members/`
   file stays refused (scenarios 1–2).

---

### User Story 4 - The app knows what to show (Priority: P2)

On login, the app reads the user's profile and learns their roles and per-scope levels, so it
shows the panel only to someone with a role and hides buttons the user cannot use.

**Why this priority**: Without it the app must guess, and shows actions that end in `403`.

**Independent Test**: Read the profile as each role and as a user without a role; compare the
roles and levels returned with the matrix.

**Acceptance Scenarios**:

1. **Given** a leader, **When** they read their profile, **Then** it lists the Leader role and
   the leader's level for every scope, and no longer contains `is_admin`.
2. **Given** an administrator, **When** they read their profile, **Then** every scope shows
   `owner`.
3. **Given** a user without a role, **When** they read their profile, **Then** the role list is
   empty and no scope has a level.
4. **Given** a user with the Leader and Media roles, **When** they read their profile, **Then**
   each scope shows the higher of the two levels.

---

### User Story 5 - Roles are assigned in the Django admin (Priority: P3)

The person who already maintains accounts in the Django admin gives or removes a role from a
user there. No app screen does this.

**Why this priority**: Required to use the feature, but it reuses the existing admin site.

**Independent Test**: In the Django admin, add the Media role to a user; their next request
reflects it.

**Acceptance Scenarios**:

1. **Given** the Django admin, **When** a role is added to a user, **Then** the user's next
   request is authorized with that role's levels.
2. **Given** a user who receives any role, **When** they try the Django admin, **Then** access
   depends only on the Django admin flag set by hand, never on the role.

---

### Edge Cases

- **User without a profile row**: roles belong to the account, not to the profile, so a missing
  profile row changes nothing about panel access — only about membership, which stays `False`.
  (Before this feature it meant "not an admin", because the flag lived on the profile.)
- **Unauthenticated request** to a management endpoint: `401`, as today (authentication is
  checked before permission).
- **Two roles**: union, never intersection. Leader + Media on `events` is `manage`.
- **Method not implemented by an endpoint** (e.g. `DELETE` on the member list): `405` for a user
  with enough level on the scope; a user without any level on the scope gets `403` first and
  learns nothing about the endpoint.
- **Declared level below the default** (e.g. a `DELETE` declared as `manage`): refused at
  import unless the endpoint names the method in `lowered=` and appears in Lowered overrides.
- **Role removed while the app is open**: the next request is refused. The profile the app holds
  may be stale until it is read again; the backend check is the only authority.
- **Media cache**: a leader who loses the role still gets `403` on the next use of a cached
  `members/` photo, because media revalidates on every use (constitution, Caching).
- **Superuser flag**: a Django superuser (`is_superuser`) with no role has no panel access and
  no level on any scope. Only roles count. Django's own permission check grants every permission
  to an active superuser, so the scope check deliberately does not rely on that shortcut. A
  superuser who needs the panel is given the Admin role (FR-030).

## Requirements *(mandatory)*

### Functional Requirements

**Levels and scopes**

- **FR-001**: The system MUST define the levels `view` < `manage` < `owner`, each including the
  lower ones.
- **FR-002**: The system MUST define the scopes `members`, `schedule`, `songs`, `gallery`,
  `events`, `notices` and `reports.hymnal_history`.
- **FR-003**: Each management endpoint MUST declare exactly one scope.
- **FR-004**: The required level MUST default from the request method (`GET` → `view`;
  `POST`/`PUT`/`PATCH` → `manage`; `DELETE` → `owner`).
- **FR-005**: An endpoint MUST be able to declare a higher required level, per method; a lower
  one MUST NOT take effect unless the method is named in `lowered=` and the endpoint is listed
  in Lowered overrides.
- **FR-006**: A request whose caller lacks the required level on the endpoint's scope MUST be
  refused with `403` and the canonical error shape, before any business logic runs.

**Roles**

- **FR-007**: The system MUST define exactly three roles — Admin, Liderança, Mídia — with the
  levels in the scope matrix.
- **FR-008**: The Admin role MUST be `owner` of every scope, present or future, without relying
  on any stored permission.
- **FR-009**: The Leader role MUST NOT hold `owner` on any scope except `gallery` (raised by
  feature 013).
- **FR-010**: A user's level on a scope MUST be the highest level any of their roles gives.
- **FR-011**: Membership (`is_member`) MUST NOT grant any role or level, and holding a role MUST
  NOT require membership.
- **FR-012**: Member-facing endpoints and the member permission MUST keep their current
  behaviour, except the member list (FR-031).

**Endpoints**

- **FR-013**: Every endpoint listed in Endpoint Classification MUST require the scope and level
  given there.
- **FR-014**: The hymnal history configuration writes MUST require `owner` on
  `reports.hymnal_history`.
- **FR-015**: Endpoints that are public today (song lists, chord chart and lyrics reads, hymnal
  settings read, hymnal event ingest) MUST stay public.
- **FR-016**: The old administrator permission MUST be removed; no endpoint may still check
  `is_admin`.

**Protected media**

- **FR-017**: Access to files under `members/` MUST require `view` on `members`, replacing the
  `is_admin` rule. Admin and Leader read them; Media does not.
- **FR-018**: The rules for `gallery/` and `profiles/` (membership, plus the owner exception)
  MUST NOT change.

**Profile**

- **FR-019**: The profile read MUST return the user's roles, each with its identifier and
  pt-BR display name.
- **FR-020**: The profile read MUST return the user's level on every defined scope, with no
  level for scopes the user cannot reach.
- **FR-021**: The profile read MUST NOT return `is_admin`.
- **FR-022**: Roles and levels MUST be read-only through the profile update.

**Migration**

- **FR-023**: Every profile with `is_admin=True` MUST be given the Admin role; profiles with
  `is_admin=False` MUST get no role.
- **FR-024**: After the conversion the `is_admin` data MUST be removed.
- **FR-025**: The deploy itself MUST create the three roles, with Leader and Media already
  holding their scope-matrix levels. No manual step in the Django admin, and no role that exists
  but holds nothing — an empty Leader or Media role would deny every request with no error to
  explain why. Admin holds nothing stored (FR-008).

**Assignment and Django admin**

- **FR-026**: Roles MUST be assignable and removable only through the Django admin. No API
  endpoint assigns roles.
- **FR-027**: Django admin access MUST stay a separate flag, set by hand, and MUST NOT be derived
  from any role.

**Security and data**

- **FR-028**: The permission decision MUST stay outside the business layer: services never learn
  about roles, scopes or request methods.
- **FR-029**: Specs 009, 010, `specs/members/spec.md`, `specs/accounts/spec.md`,
  `specs/songs/spec.md`, `specs/schedule/spec.md`, `specs/006-hymnal-view-history/spec.md` and
  `specs/constitution.md` MUST be updated to the role/scope terminology, stating what each role
  may do (e.g. member deletion requires `owner`, so only Admin).
- **FR-030**: The Django superuser flag MUST NOT grant any role or level; a user's levels come
  from their roles alone.
- **FR-031**: `GET api/members/` MUST accept a member or a caller with `view` on
  `schedule`. Found after implementation: the schedule screen loads this list, and roles do
  not require membership, so a non-member Liderança got 403 there.

### Accepted Risks

Decided with the requester; recorded, not to be re-raised.

- **Leader overwrites the monthly schedule.** Saving a month replaces the whole month. The
  existing guard against changing past schedules still applies.
- **Leader replaces Sunday plays.** Registering plays for a date can replace what was there.
- **Leader changes a member's roll status** (dismissal, transfer, etc.).
- **Leader sees member photos.**
- **`manage` can overwrite, not only create.** There is no change history outside members; a
  broader audit of changed and deleted data is left for a future feature.
- **The app breaks until updated.** Removing `is_admin` from the profile breaks the current app
  version; the app ships together with this feature.
- **Group levels are editable in the Django admin.** Whoever maintains roles there can change
  what Leader and Media hold, including giving Leader `owner`. Only Admin is fixed in code.

### Key Entities

- **Role**: a named bundle of scope levels. Three fixed values (Admin, Liderança, Mídia). A user
  account holds zero or more roles.
- **Scope**: a feature area of the management panel (`members`, `schedule`, …, `reports.<name>`).
- **Scope permission**: the pair (scope, level) a role holds. Admin holds none stored — its
  levels are implied.
- **Profile** (existing): loses `is_admin`; keeps `is_member`, which remains independent of
  roles.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of the users who managed the panel before the deploy can still perform every
  action they could before, with no manual step after deploy.
- **SC-002**: 0 delete operations succeed for a user holding only the Leader role, across every
  classified endpoint outside scope `gallery`.
- **SC-003**: A user holding only the Media role gets 0 records from the membership roll and 0
  member photos; the tag picker (feature 015) gives them names and ids only, no other field.
- **SC-004**: For every combination of role (Admin, Leader, Media, none) × scope × method in the
  classification, the outcome matches the matrix — each combination covered by an automated
  check.
- **SC-005**: Adding a new scope requires no change for the Admin role to reach it.
- **SC-006**: The app can decide whether to show the panel, and which actions to show, from a
  single profile read.

## Assumptions

- **The profile read is `GET api/me/profile/`** — the request's "`/profile`".
- **The profile lists every defined scope**, reserved ones (`events`, `notices`) included, so
  the app can prepare their screens; Admin shows `owner` on all of them.
- **Hymnal report reads stay open to every panel role**, as the matrix says; the data is not
  sensitive.
- **Status codes and error shape are the existing ones**: `401` unauthenticated, `403`
  `PERMISSION_DENIED` for missing level.
- **A user with a role but without membership** still sees member-only content only if flagged a
  member, as today with `is_admin`.
- **Implementation choices already made** (recorded here so planning does not reopen them; they
  belong in `plan.md`): Django's native groups and permissions, with custom per-scope/level
  permissions declared in model metadata rather than the automatic per-model ones; one generic
  scope permission in `core/http/permissions.py` deriving the level from the method with a
  per-view override; data migrations, each with its reason at the top of the file, that
  (a) create the three groups and attach the Leader and Media matrix permissions and (b) convert
  `is_admin` into Admin group membership, then removal of the column. Caveat for (a): Django
  creates the rows for `Meta.permissions` in a `post_migrate` signal, after every migration has
  run, so on a fresh database they do not exist yet while (a) runs. Depending on the migration
  that declares them is not enough — (a) must create the permission rows itself (get-or-create)
  before attaching them.

## Out of Scope

- The events and notices features. (Gallery write endpoints: feature 013.)
- Assigning roles from the app.
- Change history or audit outside members.
- Android app changes (separate repository).
- Changing `is_member` or the member permission.
