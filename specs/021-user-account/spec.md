# Feature Specification: User Account

**Feature Branch**: `021-user-account`

**Created**: 2026-10-21

**Status**: Draft

**Input**: User description: "Conta do usuário (backend; feature 016 in the app): the profile also
returns `has_password`, `username` and `date_joined`; edit name; remove photo; change password
(new endpoint, signs out other sessions, keeps the current one with a new pair, throttle and
lockout); delete account (new endpoint, confirmed with the password or a fresh Google `id_token`
of the same account; deletes User, Profile, photo file, push device tokens, blacklists refresh
tokens; keeps `members.Member`; immediate; throttle); a web deletion page served by Django at
`/ipbcb/conta/excluir/` (username + password, or Google for password-less accounts; CSRF;
throttle). Reason: Google Play requires account deletion inside the app **and** through a web
link. Out of scope: e-mail, renaming `is_member`, access requests, creating a password for a
Google-only account." Contract points the request left open were settled with the app's Claude
Code session on 2026-10-21; see Clarifications.

## Context

The app has an account screen that shows who is signed in and lets the person change their
photo. Google Play's data-safety policy requires any app that lets people create an account to
also let them **delete** it, both from inside the app and from a web page reachable without
installing the app. This feature adds account deletion on both surfaces, password change, and
the profile fields the account screen needs ("No app desde mês/ano", whether a password exists,
the username used to sign in).

An account **has a password** when its stored password is usable. An account created by the
first Google sign-in is born without one. Google sign-in also enters an existing account that has
a password and the same e-mail, so every rule here looks at **the account**, never at how the
person signed in this time.

### Relation to other specs

- **`specs/accounts/spec.md`** — the domain spec. Updated by this feature with the new fields,
  endpoints, page, business rules and errors.
- **`specs/008-login-brute-force-lockout/`** and the constitution's Authentication section —
  every path that checks a password is behind the failed-attempt lockout. Password change,
  API deletion and the web page all check a password, so they join the lockout (FR-012).
- **`specs/017-sunday-setlist-push/`** — push device tokens belong to the account and go with it.
- **`specs/015-gallery-member-tags/`** — the profile's link to the church roll (`member_id`)
  disappears with the profile; the roll record itself stays.

## Clarifications

### Session 2026-10-21 (with the app's Claude Code session)

- Q: Password re-checks need the lockout, which needs the HTTP request inside a service — only
  `LoginService.login()` may take one today. → A: add a second named exception,
  `LoginService.verify_password(user, password, request)`, keyed like sign-in on
  (username, address); amend the constitution to record it.
- Q: Endpoints? → A: `POST api/me/password/` → `200 {access, refresh}`; `POST api/me/delete/`
  with `{password}` or `{id_token}` → `204`. `POST`, not `DELETE`, because a secret travels in the
  body. The contract must say plainly that the caller's current access token dies at once on a
  password change and the app must switch to the pair in the response.
- Q: Error codes? → A: wrong password `400 INVALID_PASSWORD`; no password to change
  `409 PASSWORD_NOT_SET`; wrong confirmation method or missing field `400 VALIDATION_ERROR`;
  bad Google token `400 INVALID_GOOGLE_TOKEN` (not 401, which the app reads as an expired
  session); Google token of another account `403 GOOGLE_ACCOUNT_MISMATCH`; lockout
  `429 ACCOUNT_LOCKED` (existing).
- Q: How is "same account" decided for a Google token? → A: by account identity, not by
  comparing e-mail text: the token must resolve, through the same lookup Google sign-in uses
  (by e-mail), to **this** user.
- Q: Web Google button — new credential? → A: no. The app's server client ID is the existing
  Web-type `GOOGLE_CLIENT_ID`; the page uses it. Manual step for the maintainer: add the site
  origin under "Authorized JavaScript origins" in Google Cloud Console.
- Q: Google button used for an account that has a password? → A: refused; the page asks for
  username and password ("always the account").
- Q: Superusers? → A: deletion refused with `409 ACCOUNT_DELETION_BLOCKED` on both surfaces.
  Accounts with the Admin role (group) delete normally.
- Q: References to the account? → A: no migration; document them (table below). The admin
  `LogEntry` cascade is acceptable: superusers cannot delete themselves, and other accounts
  rarely have admin history.
- Q: `date_joined` format? → A: date `"YYYY-MM-DD"` in `America/Sao_Paulo`.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Delete my account from the app (Priority: P1)

A signed-in person opens the account screen, chooses "Excluir conta", types "EXCLUIR" (app-only
safeguard) and confirms who they are: with their current password if the account has one, or by
signing in with Google again if it does not. The account and everything personal attached to it
is removed immediately and the app returns to the signed-out state.

**Why this priority**: it is the Google Play requirement that blocks publishing.

**Independent Test**: create an account with a photo and a registered push device, delete it
with the right confirmation, then verify sign-in fails, the photo file is gone, no device token
remains and the church roll record linked to it still exists.

**Acceptance Scenarios**:

1. **Given** an account with a password, **When** it asks for deletion with its correct
   password, **Then** the account, its profile, its photo file and its device tokens are removed,
   every refresh token it held stops working, and the answer is success with no body.
2. **Given** an account with a password, **When** it asks for deletion with a wrong password,
   **Then** nothing is removed and the answer says the password is wrong, without signing the
   person out of the app.
3. **Given** an account without a password, **When** it asks for deletion with a fresh Google
   token for the same account, **Then** the account is removed as in scenario 1.
4. **Given** an account without a password, **When** it sends a Google token that belongs to a
   different Google account, **Then** nothing is removed and the answer says the Google account
   does not match.
5. **Given** an account linked to a church roll record, **When** it is deleted, **Then** the roll
   record is unchanged and simply has no account linked any more.
6. **Given** photos, tags, events, setlists or roll-change history authored by the account,
   **When** it is deleted, **Then** that content stays and shows no author.
7. **Given** repeated wrong passwords, **When** the lockout threshold is reached, **Then** further
   attempts are refused for the lockout period, as on the login screen.

---

### User Story 2 - Delete my account through a web link (Priority: P1)

Someone who no longer has the app (or never reinstalled it) opens the deletion link published in
the Play Store listing, signs in on that page with username and password — or with the Google
button if the account has no password — confirms, and the account is deleted exactly as in
User Story 1.

**Why this priority**: the other half of the Google Play requirement.

**Independent Test**: open the page in a browser, sign in with a test account, confirm, and check
the same outcome as User Story 1; repeat with a Google-only test account through the Google
button.

**Acceptance Scenarios**:

1. **Given** the page is opened, **When** it loads, **Then** it explains in Portuguese what is
   deleted and what is kept, and offers a username + password form and a Google button.
2. **Given** a valid username and password and the confirmation ticked, **When** the form is
   sent, **Then** the account is deleted and a confirmation page is shown.
3. **Given** a wrong username or password, **When** the form is sent, **Then** a generic
   "usuário ou senha inválidos" message is shown and nothing is deleted.
4. **Given** a Google-only account, **When** the person signs in with the Google button for the
   same account and confirms, **Then** the account is deleted.
5. **Given** an account with a password, **When** the person uses the Google button, **Then**
   nothing is deleted and the page asks for username and password instead.
6. **Given** a form sent without the page's anti-forgery token, **When** it arrives, **Then** it
   is refused and nothing is deleted.
7. **Given** too many submissions from one client, **When** the rate limit is reached, **Then**
   the page says to try again later.

---

### User Story 3 - Change my password (Priority: P2)

A signed-in person whose account has a password opens "Trocar senha", enters the current
password, the new one and its confirmation. The password changes, every other device signed into
the account is signed out, and the device where the change was made stays signed in.

**Why this priority**: the account screen's second action, and the answer to a lost or shared
device.

**Independent Test**: sign in on two clients, change the password on one, check the other client
can neither call the API nor refresh, and the first keeps working with the tokens it received.

**Acceptance Scenarios**:

1. **Given** an account with a password signed in on two devices, **When** device A changes the
   password with the correct current password, **Then** device A receives a new pair of tokens
   that work, and device B's access and refresh tokens stop working.
2. **Given** a wrong current password, **When** the change is requested, **Then** nothing changes
   and the answer says the current password is wrong, without signing the person out.
3. **Given** a new password shorter than 6 characters, or a confirmation that differs, **When**
   the change is requested, **Then** nothing changes and the answer names the offending field
   with the same messages as registration.
4. **Given** an account without a password, **When** the change is requested, **Then** it is
   refused with a clear message that the account has no password.
5. **Given** repeated wrong current passwords, **When** the lockout threshold is reached,
   **Then** further attempts are refused for the lockout period.

---

### User Story 4 - See my account details (Priority: P2)

The account screen shows the username the person signs in with, "No app desde mês/ano", and only
offers "Trocar senha" when the account has a password.

**Why this priority**: the screen cannot decide what to show without it; the change is additive.

**Independent Test**: read the profile of a password account and of a Google-only account and
compare `has_password`, `username` and `date_joined`.

**Acceptance Scenarios**:

1. **Given** an account created with username and password, **When** the profile is read, **Then**
   it includes the username, `has_password` true and the date the account was created.
2. **Given** an account created by Google sign-in, **When** the profile is read, **Then**
   `has_password` is false.
3. **Given** an app version that does not know the new fields, **When** it reads the profile,
   **Then** it keeps working (fields are only added, none removed or renamed).

---

### User Story 5 - Edit my name and remove my photo (Priority: P3)

Already available; this feature confirms and covers the contract the account screen relies on:
the display name can be edited (trimmed, not empty, at most 100 characters) and the photo can be
removed, which also removes the file.

**Why this priority**: existing behaviour; only confirmation and tests.

**Independent Test**: edit the name with surrounding spaces, with only spaces and with 101
characters; remove a photo and check the file is gone.

**Acceptance Scenarios**:

1. **Given** a name with surrounding spaces, **When** it is saved, **Then** it is stored trimmed.
2. **Given** an empty or whitespace-only name, **When** it is saved, **Then** it is refused.
3. **Given** a name longer than 100 characters, **When** it is saved, **Then** it is refused.
4. **Given** a profile with a photo, **When** the photo is removed, **Then** the profile has no
   photo and the file no longer exists in storage.

### Edge Cases

- A Google-only account sends a password, or a password account sends a Google token, to the
  deletion endpoint: refused as a validation error naming what this account needs.
- The deletion request carries neither a password nor a Google token: validation error.
- The account is deleted while another device still holds an access token: that token stops
  working on its next request (its user no longer exists); its refresh token is refused.
- The deletion is retried after success (network retry): the caller's token no longer
  authenticates, so the retry is refused as unauthenticated; nothing else happens.
- Photo file already missing from storage when the account is deleted: deletion still succeeds.
- An expired or tampered Google token: refused, nothing deleted.
- A Google token whose e-mail is not verified: refused like at sign-in.
- Password change where the new password equals the current one: accepted (no complexity or
  reuse rule — constitution).
- Superuser account asking for deletion: refused (FR-019).
- The web page receives a username with different case or spaces: normalised like at sign-in.

## Requirements *(mandatory)*

### Functional Requirements

**Profile**

- **FR-001**: The profile read MUST also return `username`, `has_password` (whether the account's
  stored password is usable) and `date_joined` (the calendar date the account was created, in
  the church's time zone). The values MUST also be returned by the profile edit response.
- **FR-002**: The new fields MUST be read-only; values sent in an edit are ignored.
- **FR-003**: The profile edit MUST accept `name`, store it trimmed, and refuse an empty or
  whitespace-only name and one longer than 100 characters.
- **FR-004**: Removing the photo MUST remove the file from storage, not only the reference.

**Password change**

- **FR-005**: A signed-in account with a password MUST be able to change it by sending the current
  password, the new password and a confirmation.
- **FR-006**: The new password MUST follow the registration rules: at least 6 characters, the
  confirmation equal to it, the same messages; no other rule.
- **FR-007**: After a change, every refresh token the account held MUST stop working, every access
  token issued before the change MUST stop working, and the response MUST carry a new access and
  refresh token that work.
- **FR-008**: An account without a password MUST receive a clear refusal ("Esta conta não tem
  senha.") and nothing changes. Creating a password is out of scope.

**Account deletion**

- **FR-009**: A signed-in account MUST be able to delete itself, confirming with its current
  password when it has one, or with a fresh Google token of the same account when it has none.
  The other confirmation method MUST be refused for that account.
- **FR-010**: A Google token is valid for deletion only if it passes the same checks as Google
  sign-in (signature, audience, expiry, verified e-mail) and its e-mail is the account's e-mail.
- **FR-011**: Deletion MUST remove, at once and with no grace period: the account, its profile,
  the profile photo file, its push device tokens, its role assignments, and MUST make every
  refresh token it held unusable. It MUST NOT remove the church roll record the profile was
  linked to.
- **FR-012**: Every step that checks a password (password change, API deletion, web page) MUST be
  under the same failed-attempt lockout as sign-in, keyed on the same (username, client address)
  pair.
- **FR-013**: Content the account authored elsewhere (gallery photos and tags, trash entries,
  events, setlists, roll-change history, hymnal view history) MUST stay, with no author.
- **FR-014**: Password change, deletion and the web page MUST be rate-limited like the sign-in
  endpoints.
- **FR-015**: Wrong passwords and Google mismatches MUST NOT be answered as "not authenticated",
  so the app does not treat them as an expired session.

**Web deletion page**

- **FR-016**: The server MUST serve a public page, in Portuguese, under the application's base path
  (`/ipbcb/conta/excluir/`), explaining what is deleted and kept, and letting the person
  identify themselves with username and password, or with Google for an account without a
  password, tick a confirmation, and delete the account with the same effects as FR-011.
- **FR-017**: The page's form MUST be protected against cross-site request forgery, and a failed
  sign-in on it MUST show a generic message that does not reveal whether the username exists.
- **FR-018**: After a deletion the page MUST show a confirmation; the person is never left signed
  in on the page.
- **FR-019**: Deletion of a superuser account MUST be refused on both surfaces with a message to
  ask the church's leadership, so the Django admin is never lost by accident. Accounts holding
  the Admin role delete normally.
- **FR-020**: A Google token "of the same account" means the token resolves, through the lookup
  Google sign-in uses, to the account asking — not a textual comparison of e-mails.

### Key Entities

- **Account (User)**: username, e-mail, password (usable or not), creation date, active flag,
  roles. Deleted by this feature.
- **Profile**: display name, photo, membership flag, link to the roll. Deleted with the account.
- **Device token**: push registration of one phone for one account. Deleted with the account.
- **Refresh token record**: issued refresh tokens and their blacklist. Revoked on password change
  and deletion; the record survives without an owner, as the token library keeps it.
- **Church roll record (Member)**: church data. Never deleted by this feature.

### References to the account kept after deletion (all become "no author")

| Where | Reference | On account deletion |
|-------|-----------|---------------------|
| accounts `Profile.user` | owner | deleted (cascade) |
| core `DeviceToken.user` | owner | deleted (cascade) |
| Django `User.groups` / `user_permissions` | role links | deleted (link rows only) |
| Django admin `LogEntry.user` | admin history | deleted (cascade, Django's own) |
| simplejwt `OutstandingToken.user` | issued tokens | kept, owner cleared; blacklisted first |
| gallery `Photo.uploaded_by` | author | kept, cleared |
| gallery `PhotoTag.tagged_by` | author | kept, cleared |
| gallery `TrashEntry.deleted_by` | author | kept, cleared |
| events `Event.created_by` | author | kept, cleared |
| members `MemberChangeLog.editor` | author | kept, cleared |
| songs `Setlist.saved_by` | author | kept, cleared |
| songs `HymnalViewEvent.user` | viewer | kept, cleared (becomes anonymous) |
| accounts `Profile.member` → `Member` | roll link | the profile row goes; the Member stays |

No schema change is needed: every reference already has the behaviour above. The admin
`LogEntry` cascade is accepted: superusers cannot delete themselves (FR-019), and other accounts
rarely have admin history.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A person can delete their account from the app in under 1 minute, and from the web
  link in under 2 minutes, with no contact with the church.
- **SC-002**: After a deletion, 0 personal records of the account remain (account, profile, photo
  file, device tokens), and 100% of its previously issued tokens are refused.
- **SC-003**: After a deletion, 100% of the church roll records and authored content that existed
  before are still present.
- **SC-004**: After a password change, the other devices are refused on their very next request,
  and the device that made the change continues without signing in again.
- **SC-005**: The app's current published version keeps working against the new profile response
  with no update.

## Assumptions

- The Play Store listing will point at `https://<domain>/ipbcb/conta/excluir/`; the domain is
  configuration, never hardcoded.
- The app requires typing "EXCLUIR" before calling deletion; the server does not check it.
- The web page uses Google's own sign-in button in the browser with the existing OAuth client;
  enabling it needs the site's origin registered on that client (manual configuration outside
  the code).
- Deleted accounts are not recoverable; there is no backup restore flow for a single account.
- E-mail is not shown, edited or used for anything new (known risk of e-mail-based Google
  linking — not widened here).
