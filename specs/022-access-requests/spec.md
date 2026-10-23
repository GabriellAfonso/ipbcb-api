# Feature Specification: Member Access and Access Requests

**Feature Branch**: `022-access-requests`

**Created**: 2026-10-21

**Status**: Draft

**Input**: User description: "Member access + access requests (backend; the app spec comes
later). Rename `is_member` → `member_access` (`IsMemberUser` → `HasMemberAccess`); `/me` sends both
names for 1–2 app versions. No member role: `HasMemberAccess` = the flag OR an Admin/Liderança
role (fixes the 'Gerar Escala' 403 for leaders without the flag). `AccessRequest` (user, type
`access` | `data_correction`, message, status pending/approved/denied, decided_by, decided_at,
optional denial reason, created_at); one pending request per user per type; 1 request per 24 h
rolling per user → 429. `access_requests_blocked` on the profile ('Pedidos de acesso
indisponíveis. Fale com a liderança.'). Management 'Perfis' (app accounts, distinct from
'Membros' = the roll): new scope `profiles`, only Admin + Liderança; Pendentes / Todos; detail:
approve, deny (optional reason), revoke access, block/unblock requests, link the account to a roll
member. Approving `access` sets `member_access`; a `data_correction` request is closed by leaders,
who fix the roll themselves. Push: leaders on a new request; requester on approval and on denial
(with reason); none on revocation. `/me`: access status (Liberado / Aguardando / Não liberado),
`access_requests_blocked`; read-only roll data (cargo, ministérios, aniversário, batismo, gênero)
when `member_id` is linked — the app keeps it in memory only and snapshots `/me` to disk, so
decide where it goes. Nothing may let a user set or edit an e-mail."

All decisions above were settled by the requester; the points the request left open were decided
while writing this spec and are listed under Clarifications.

## Context

The app gates church content (roll, birthdays, schedule, gallery, members-only events and media)
behind a per-account flag that today is called `is_member`. The account also has a separate link
to its record on the church roll (`Profile.member`). The two are independent — an account may
see the content without being linked, and be linked without seeing it — but the name made people
read the flag as "is linked to the roll". This feature renames the flag to **member access**,
makes the leadership roles carry it implicitly, and adds the missing workflow: today a person who
installs the app and sees locked screens has no way to ask for access other than finding a leader
in person, and leaders grant it in the Django admin.

Two words are kept apart throughout:

- **Perfis** — app accounts (who signed up in the app). Managed by this feature.
- **Membros** — the church roll (`specs/members/`). Unchanged, except that an account can now be
  linked to a roll record from the panel.

### Relation to other specs

- **`specs/012-feature-role-permissions/`** — roles and scopes. This feature adds the scope
  `profiles` (Admin `owner`, Liderança `manage`, Mídia none) and changes "membership is a separate
  axis and never grants a level" to its mirror: **a level never needs member access, and the Admin
  and Liderança roles imply member access** (FR-003).
- **`specs/015-gallery-member-tags/`** — `Profile.member` was set only in the Django admin. It can
  now also be set from the panel (FR-020), with the same uniqueness rule.
- **`specs/017-sunday-setlist-push/`** — the device registry and the push sender are reused; three
  new message types.
- **`specs/021-user-account/`** — account deletion removes the account's access requests; requests
  it decided keep their decision with no decider.
- **`specs/members/spec.md`** — the roll is sensitive personal data (constitution). Showing a
  person their own roll record is a new read of it, under the same rules.

## Clarifications

### Decided while writing the spec (requester's decisions applied, gaps filled)

- Q: Is `member_access` in `/me` the stored flag or the effective access? → A: the **effective**
  access (flag OR Admin/Liderança role), so a leader never sees a locked screen. `is_member` carries
  the same value. The panel shows both the stored flag and whether a role grants it.
- Q: Does the 24 h limit count per type? → A: no, per account across both types, as stated: one
  request of any type per rolling 24 hours. Denied requests count.
- Q: Order of refusals when creating a request? → A: blocked (403) → access already granted
  (409, `access` only) → same type already pending (409) → 24 h limit (429). A blocked account is
  told it is blocked even if it would also be rate limited.
- Q: Where does the roll data go? → A: a separate endpoint, `GET api/me/member/`, never in
  `/me`: the app writes `/me` to disk (ETag snapshot) and roll data is sensitive. The new endpoint
  is `private, no-store` with no ETag. `/me` keeps only `member_id`.
- Q: What does "approve" mean for a data correction? → A: "resolved". The status becomes
  `approved`, nothing changes on the account or the roll, and the requester gets the approval push.
  The wire status stays `approved` so both types share one shape; the app labels it.
- Q: Does blocking cancel pending requests? → A: no. Leaders still decide them; the block only
  stops new ones.
- Q: Does revoking cancel a pending `access` request or block? → A: no. Revocation clears the
  flag only, with no push.
- Q: Who receives the "new request" push? → A: every active account with `manage` on `profiles`
  (Admin and Liderança), except the requester.
- Q: Which accounts appear under "Todos"? → A: every active account, including leaders. Inactive
  accounts cannot sign in and are left out.
- Q: Push payload with a denial reason — does it break "no user data in pushes" (spec 017
  FR-011)? → A: the reason is text a leader wrote to that person and goes only to that person's
  devices. It is the one free-text value a push may carry; no name, no roll field, no e-mail.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Ask for access from a locked screen (Priority: P1)

A person signed into the app without member access opens a locked screen and taps "Pedir acesso",
optionally writing a message ("Sou membro desde 2010, frequento o culto das 18h"). The request
reaches the leaders, and the person's profile shows "Aguardando" until someone decides.

**Why this priority**: it is the gap that makes new accounts useless without a leader in person.

**Independent Test**: as an account without access, create an `access` request with and without a
message; read `/me` and see `access_status` "pending"; try again and get the "already pending"
refusal.

**Acceptance Scenarios**:

1. **Given** an account without member access, not blocked and with no request in the last 24 h,
   **When** it asks for access with or without a message, **Then** a pending request is stored and
   the answer returns it.
2. **Given** that pending request, **When** the profile is read, **Then** the access status is
   "pending".
3. **Given** a pending `access` request, **When** the account asks again, **Then** it is refused as
   already pending and nothing is stored.
4. **Given** an account that already has member access (by flag or by role), **When** it asks for
   access, **Then** it is refused as already granted.
5. **Given** an account that made any request less than 24 hours ago, **When** it asks again,
   **Then** it is refused as too soon, with how long to wait.
6. **Given** an account blocked from requests, **When** it asks, **Then** it is refused with
   "Pedidos de acesso indisponíveis. Fale com a liderança."
7. **Given** a new request, **When** it is stored, **Then** every Admin and Liderança account
   receives a push on its registered devices.

---

### User Story 2 - Leaders decide requests in "Perfis" (Priority: P1)

A leader opens "Perfis" in the panel, sees "Pendentes" (accounts with a request waiting, oldest
first) and "Todos" (every account). Opening one shows the account, its access, its link to the
roll and its request history. The leader approves or denies a request, optionally with a reason.

**Why this priority**: without the decision, requests go nowhere.

**Independent Test**: as Liderança, list pending, approve one `access` request and see the account
gain member access; deny another with a reason; as Mídia, get 403 on every endpoint.

**Acceptance Scenarios**:

1. **Given** pending requests, **When** a leader lists "Pendentes", **Then** only accounts with a
   pending request appear, oldest request first, each with its pending requests.
2. **Given** any accounts, **When** a leader lists "Todos", **Then** every active account appears,
   ordered by name.
3. **Given** a pending `access` request, **When** a leader approves it, **Then** the request is
   approved with who and when, the account's member access is set, and the requester gets a push.
4. **Given** a pending request, **When** a leader denies it with or without a reason, **Then** it
   is denied with who, when and the reason, the account is unchanged, and the requester gets a push
   carrying the reason.
5. **Given** a pending `data_correction` request, **When** a leader approves (resolves) it,
   **Then** it is closed as approved and nothing else changes; the requester gets a push.
6. **Given** a request already decided, **When** a leader tries to decide it again, **Then** it is
   refused as no longer pending.
7. **Given** an account with Mídia only, or no role, **When** it calls any "Perfis" endpoint,
   **Then** it is refused.

---

### User Story 3 - Leaders manage an account's access and link (Priority: P2)

From the account's detail a leader grants or revokes member access, blocks or unblocks the account
from making requests, and links the account to its record on the roll (or removes the link).
Granting needs no request: a leader who knows the person (an old member, someone just received)
turns access on directly, like assigning a role, without making them find a locked screen first.

**Why this priority**: the controls that keep the workflow from being abused and that replace the
Django admin for daily work.

**Independent Test**: grant access to an account without a request and see content endpoints
allow it, the granting leader recorded and the "Acesso liberado" push sent; revoke it and see
content endpoints refuse it, with no push; block it and see a request refused; link it to a member and see `member_id` in its `/me`;
link a second account to the same member and get a conflict.

**Acceptance Scenarios**:

1. **Given** an account with member access, **When** a leader revokes it, **Then** the stored flag
   is cleared, its next request to member content is refused, and no push is sent.
2. **Given** an account, **When** a leader blocks it, **Then** its new requests are refused;
   **When** unblocked, **Then** they are accepted again (subject to the other rules).
3. **Given** a roll member not linked to any account, **When** a leader links an account to it,
   **Then** the account's `member_id` is that member.
4. **Given** a member already linked to another account, **When** a leader links a second account
   to it, **Then** it is refused as a conflict and nothing changes.
5. **Given** a linked account, **When** a leader removes the link, **Then** `member_id` is null and
   the roll record is unchanged.
6. **Given** a member id that does not exist, **When** a leader links to it, **Then** it is
   refused naming the field.
7. **Given** an account without the stored flag and without a pending request, **When** a leader
   grants access, **Then** the flag is set, the leader and the moment are recorded as the grant,
   and the account gets the approval push.
8. **Given** an account with a pending `access` request, **When** a leader grants access directly,
   **Then** that request is approved by the same leader (it leaves Pendentes) and the push names
   it.
9. **Given** an account whose stored flag is already set, **When** a leader grants access,
   **Then** nothing changes and no push is sent.

---

### User Story 4 - Leaders see member content without the flag (Priority: P2)

An account holding the Admin or Liderança role sees every member-gated screen, whatever its flag —
in particular "Gerar Escala", which today answers 403 to a leader without the flag.

**Why this priority**: a live bug, fixed by the same rule that defines member access.

**Independent Test**: a Liderança account with the flag off reads the schedule, the roll list, the
birthdays and the gallery; a Mídia account with the flag off is refused.

**Acceptance Scenarios**:

1. **Given** an Admin or Liderança account without the flag, **When** it calls a member-gated
   endpoint, **Then** it is allowed.
2. **Given** a Mídia account without the flag, **When** it calls a member-gated endpoint, **Then**
   it is refused.
3. **Given** a Liderança account without the flag, **When** it reads `/me`, **Then**
   `member_access` (and `is_member`) is true and `access_status` is "granted".

---

### User Story 5 - Ask for a correction of my roll data (Priority: P2)

A person whose account is linked to the roll sees their roll data on the profile (cargo,
ministérios, aniversário, batismo, gênero), read-only. If something is wrong they tap "Solicitar
correção" and describe it; leaders fix the roll themselves and close the request.

**Why this priority**: the profile screen's new card and its one action.

**Independent Test**: link an account to a member with a role, ministries, birthday, baptism and
gender; read `api/me/member/`; create a `data_correction` request without a message (refused) and
with one (stored); approve it as a leader and see nothing on the roll change.

**Acceptance Scenarios**:

1. **Given** a linked account, **When** it reads its roll data, **Then** it gets the cargo name,
   the ministry names, the birthday parts known, the baptism date and the gender, and the response
   tells every cache not to store it.
2. **Given** an account without a link, **When** it reads its roll data, **Then** it is told there
   is no linked record.
3. **Given** a `data_correction` request without a message, **When** it is sent, **Then** it is
   refused naming the field.
4. **Given** a `data_correction` request with a message, **When** it is sent, **Then** it is stored
   pending and leaders get the push, under the same block, pending and 24 h rules as `access`.

---

### User Story 6 - Older app versions keep working (Priority: P3)

The published app reads `is_member` from `/me`. It keeps reading it, with the same value as
`member_access`, until the next app versions have moved.

**Independent Test**: read `/me` and compare `is_member` and `member_access` for a flag account, a
leader without the flag and an account with nothing.

**Acceptance Scenarios**:

1. **Given** any account, **When** `/me` is read, **Then** `is_member` equals `member_access`.
2. **Given** a `PATCH` to `/me` sending `is_member`, `member_access`, `access_status` or
   `access_requests_blocked`, **When** it is applied, **Then** they are ignored.

### Edge Cases

- Two requests of the same type sent at the same moment: one is stored, the other is refused as
  already pending (the store enforces one pending request per account and type).
- A leader approves an `access` request of an account that meanwhile got the flag another way:
  approved, flag stays set.
- A leader approves a request of an account deleted meanwhile: the request went with the account;
  the answer is "not found".
- An account deleted after deciding requests: those requests keep their decision with no decider.
- An account is revoked while its `access` request is pending: the request stays pending.
- A leader grants access directly while another leader denies the pending request at the same
  moment: the grant still sets the flag; the request keeps the other leader's decision.
- An account whose access comes only from a role is granted access: the flag is set (it keeps
  access if the role is removed later) and the push is sent.
- The flag set in the Django admin records no grant (granter and date stay empty), as do flags
  set before this feature.
- A blocked account with a pending request: the request can still be decided.
- The account's roll record is deleted: the link becomes null and `api/me/member/` answers "no
  linked record".
- A request message or denial reason with only spaces: the message is treated as absent (refused
  for `data_correction`); the reason is stored as absent.
- A leader decides a request of their own (e.g. their own `data_correction`): allowed.
- A push fails or no device is registered: the request or decision is still saved.

## Requirements *(mandatory)*

### Functional Requirements

**Member access**

- **FR-001**: The profile's content-gate flag MUST be called **member access** everywhere (stored
  field, permission, responses), stay independent of the roll link, and keep every existing value.
- **FR-002**: Member-gated endpoints MUST allow an account when its member-access flag is set **or**
  it holds the Admin or Liderança role. Mídia alone, or no role, does not grant it.
- **FR-003**: No role may require member access, and member access never grants a panel level.
  There is no "member" role.
- **FR-004**: `/me` MUST return `member_access` (the effective access of FR-002) and `is_member`
  with the same value, `access_status` (`granted` when `member_access`; else `pending` when an
  `access` request is pending; else `none`), `access_requests_blocked`, and
  `data_correction_pending`. All read-only. `is_member` stays for at least two app versions.

**Requests**

- **FR-005**: A signed-in account MUST be able to create a request of type `access` (message
  optional) or `data_correction` (message required), message at most 1000 characters, trimmed.
- **FR-006**: An account MUST NOT have more than one pending request of the same type.
- **FR-007**: An account MUST NOT create more than one request (any type) in any rolling 24-hour
  period; the refusal says how many seconds remain.
- **FR-008**: An account blocked from requests MUST be refused with "Pedidos de acesso
  indisponíveis. Fale com a liderança."
- **FR-009**: An `access` request from an account that already has member access MUST be refused.
- **FR-010**: Refusals are checked in the order blocked, already granted, already pending, 24 h.

**Management ("Perfis")**

- **FR-011**: A new management scope `profiles` MUST exist: Admin `owner`, Liderança `manage`,
  Mídia none. Every "Perfis" endpoint declares it.
- **FR-012**: Leaders MUST be able to list accounts with a pending request (oldest pending first)
  and all active accounts (by name), each with name, username, photo, stored flag, whether a role
  grants access, block flag, linked roll member (id and name) and pending requests.
- **FR-013**: Leaders MUST be able to read one account with its full request history (newest
  first), each request with type, message, status, creation date, decider, decision date and
  reason.
- **FR-014**: Approving a pending `access` request MUST set the account's member-access flag;
  approving a `data_correction` request MUST only close it. Both record decider and date.
- **FR-015**: Denying a pending request MUST record decider, date and an optional reason (at most
  500 characters, trimmed) and change nothing on the account.
- **FR-016**: Deciding a request that is not pending MUST be refused as a conflict.
- **FR-017**: Leaders MUST be able to revoke member access (clear the stored flag and the grant
  record). No push.
- **FR-017a**: Leaders MUST be able to grant member access directly, without a request: it sets
  the stored flag and records the grant (leader and moment); a pending `access` request of the
  account is approved by the same leader in the same step. The account gets the approval push
  (`request_type` `access`, with the request id when one was approved). Granting an
  account whose stored flag is already set changes nothing and sends no push.
- **FR-017b**: Every grant — approving an `access` request or granting directly — MUST record who
  granted and when, shown with the stored flag in "Perfis". Approving an `access` request of an
  account whose flag is already set keeps the earlier grant record.
- **FR-018**: Leaders MUST be able to block and unblock an account's requests.
- **FR-019**: Responses of "Perfis" MUST NOT include the account's e-mail, and no endpoint of this
  feature may accept an e-mail.
- **FR-020**: Leaders MUST be able to link an account to a roll member or remove the link; a
  member already linked to another account is a conflict; an unknown member id is a field error.

**Push**

- **FR-021**: A new request MUST notify every active account with `manage` on `profiles` except the
  requester; an approval, a direct grant and a denial MUST notify the requester (a denial with its reason, when
  given). A revocation, a block and a link notify nobody. A push never fails the operation.
- **FR-022**: Push payloads carry the message type, the request id (absent on a direct grant
  with no pending request) and type, and — on a denial —
  the reason. No name, no roll field, no e-mail.

**Roll data for the profile**

- **FR-023**: A signed-in account linked to a roll record MUST be able to read, from an endpoint
  separate from `/me`, its record's cargo, ministries, birth day/month/year, baptism date and
  gender. Responses are private and not stored (`no-store`), carry no validator, and are never
  logged with their fields. Without a link the answer is "not found" with a clear code.

**Lifecycle**

- **FR-024**: Deleting an account MUST delete its requests; requests it decided keep the decision
  with no decider.

### Key Entities

- **Profile** (accounts): gains `member_access` (renamed from `is_member`),
  `access_requests_blocked` and the grant record (`access_granted_by`, `access_granted_at`). `member` (roll link) becomes writable from the panel.
- **AccessRequest** (accounts): account, type (`access` | `data_correction`), message (nullable),
  status (`pending` | `approved` | `denied`), decided by (nullable), decided at (nullable), denial
  reason (nullable), created at. At most one pending per (account, type).
- **Member** (members): read for the account's own roll data; never written by this feature.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A person with a new account can ask for access in under 30 seconds from a locked
  screen, and leaders are notified within a minute when their device is online.
- **SC-002**: A leader can decide a pending request in under 3 taps from the "Perfis" list.
- **SC-003**: 100% of Admin and Liderança accounts reach member-gated content without the flag;
  0% of Mídia-only accounts do.
- **SC-004**: No account can create more than one request per 24 hours or hold two pending
  requests of the same type.
- **SC-005**: The current published app keeps working against the new `/me` with no update.
- **SC-006**: Roll data never appears in a cacheable response or in a log line.

## Assumptions

- The app (spec to be written separately) maps `access_status` to "Liberado" / "Aguardando" /
  "Não liberado", hides "Pedir acesso" when blocked, and keeps roll data in memory only.
- The roll-member picker in the app reuses the existing `GET api/admin/members/` (Liderança has
  `view` on `members`; Admin `owner`), so this feature adds no member search.
- Notifications are best-effort, as in spec 017.
- E-mail is not shown, accepted or changed anywhere in this feature (Google sign-in links accounts
  by e-mail — `specs/accounts/spec.md`).
- `is_member` in `/me` is removed in a later feature, once no supported app version reads it.
