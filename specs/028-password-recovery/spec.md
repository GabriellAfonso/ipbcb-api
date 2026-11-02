# Feature Specification: Password recovery by e-mail

**Feature Branch**: `028-password-recovery`

**Created**: 2026-11-02

**Status**: Implemented

**Input**: User description: "Let a person who forgot the password of a username-and-password account recover it by e-mail, on their own, with a 6-digit code. This requires storing a recovery e-mail, which is new: today password accounts have no e-mail at all." Full input, with every decision and its reason: `TODO/specify_password_recovery_backend.md`; decision conversation: session `5ea87f01-d455-45d6-a6f0-13a62f8ae10c` of the app project.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Recover a forgotten password (Priority: P1)

A person who forgot the password of their account asks for a code using only their e-mail address. They receive one message listing each account tied to that address with its own code. They type the code and a new password; that account now opens with the new password and every old session of it stops working. They go back to the login screen and sign in normally.

**Why this priority**: This is the whole purpose of the feature. Today such a person has no way back: signing in with Google creates a different account, without their member access or history.

**Independent Test**: With an account whose recovery e-mail is already stored, request a code, read it from the delivered message, reset the password, then sign in with the new password and see the old one and the old sessions refused.

**Acceptance Scenarios**:

1. **Given** an active account with a password and a recovery e-mail, **When** a code is requested for that address, **Then** the answer is the generic success and one message reaches the address naming the username and a 6-digit code.
2. **Given** two accounts sharing an address, **When** a code is requested, **Then** one single message lists both usernames, each with its own different code.
3. **Given** a valid code, **When** it is confirmed with a valid new password, **Then** the password changes, every session of the account is revoked, the code stops working, no tokens are returned and the login lockout of that username is cleared.
4. **Given** an address with no matching account, **When** a code is requested, **Then** the answer is identical to the answer for a matching address and nothing is sent.
5. **Given** a Google-only or a deactivated account holding the address, **When** a code is requested, **Then** that account gets no code.
6. **Given** a wrong, expired or already used code, **When** it is confirmed, **Then** one single generic error is returned, whichever of the three it was.
7. **Given** two accounts sharing an address, **When** one of them is recovered, **Then** the other account's code still works, and five wrong attempts in total on that address invalidate every code of the address.

---

### User Story 2 - Give an e-mail when creating a password account (Priority: P1)

A person creating a username-and-password account must type an e-mail. Nothing is sent and nothing is verified at that moment, and they enter the app as they do today.

**Why this priority**: Without it new accounts could not recover, and the recovery of Story 1 has nothing to match.

**Independent Test**: Register with and without the field; the first succeeds and stores the address trimmed and lowercased, the second is refused on that field.

**Acceptance Scenarios**:

1. **Given** a registration with `" Ana@Example.COM "`, **When** it is submitted, **Then** the account is created with `ana@example.com` as its unconfirmed recovery e-mail and no message is sent.
2. **Given** a registration with no e-mail or an invalid one, **When** it is submitted, **Then** it is refused with a Portuguese message under that field.
3. **Given** an address another account already uses, **When** registering with it, **Then** registration succeeds: the e-mail is not unique.

---

### User Story 3 - See, change and confirm the recovery e-mail while signed in (Priority: P2)

A signed-in person with a password sees their recovery e-mail and whether it is confirmed. They can set or change it by typing their current password, and can confirm it with a code sent to the address. Existing accounts that have no e-mail use this to add one. This is how a typo made at registration gets fixed.

**Why this priority**: The address is typed only once, so a typo must be correctable. Existing accounts have no other way to enable recovery.

**Independent Test**: As a signed-in password account, read the profile, change the address with the current password, request and confirm a code, and read the profile again.

**Acceptance Scenarios**:

1. **Given** an account with a password, **When** the profile is read, **Then** it shows the recovery e-mail and whether it is confirmed.
2. **Given** the correct current password and a different address, **When** the address is changed, **Then** the confirmation is cleared, pending codes of the account stop working and the sessions are kept.
3. **Given** a wrong current password, **When** the address is set or changed, **Then** it is a form error ("Senha incorreta."), nothing changes and the person stays signed in; the attempt counts toward the login lockout.
4. **Given** an unconfirmed address, **When** a code is requested and then typed correctly, **Then** the address is confirmed.
5. **Given** a Google-only account, **When** any of these actions is called, **Then** it is refused as "this account has no password".

---

### User Story 4 - The recovery e-mail never opens an account (Priority: P1)

Whatever a user types as a recovery e-mail, it never identifies an account for Google sign-in and is never a login. Someone typing a victim's address gains nothing when the victim later signs in with Google.

**Why this priority**: Without this rule the feature would open an account takeover (`TODO/alerta-email-vinculo-google.md`). It ships with the first code, not after it.

**Independent Test**: Create a password account whose recovery e-mail equals a Google address, sign in with that Google identity, and see a separate account opened.

**Acceptance Scenarios**:

1. **Given** an account whose recovery e-mail equals a Google address, **When** that Google identity signs in, **Then** it does not enter that account.
2. **Given** a recovery e-mail, **When** it is typed as a username at login, **Then** it opens nothing.

---

### Edge Cases

- **A request while a limit is hit** (address per minute or per hour, or client per hour): the public answer stays the same and nothing is sent.
- **Limits reached by a signed-in person asking for a confirmation code**: refused with the wait time, since that person already sees their own address and the answer reveals nothing about other people's accounts.
- **The account loses eligibility between request and confirmation** (deactivated, password made unusable, address changed): the code gives the generic error.
- **A new request**: invalidates the earlier codes of that purpose for each account, and the count of wrong attempts starts over with the new codes.
- **The attempt limit reached**: every recovery code of the address is invalidated, so even the correct code fails until a new request.
- **Setting the address already stored**: not a change, so the confirmation and pending codes stay.
- **Asking for a confirmation code with no address, or for an address already confirmed**: refused, nothing sent.
- **The new password fails the rules on confirmation**: a form error that neither uses the code nor counts as a wrong attempt.
- **Delivery fails**: the failure is logged without the address and the public answer has already been given; the person asks again.
- **The server restarts while a message is being sent**: the message is lost. Accepted at this volume; the person asks again.
- **A signed-out person whose stored address is wrong, or an existing account locked out with no address**: solved by hand on the server (`manage.py changepassword`). Nothing is built for it.

## Requirements *(mandatory)*

### Functional Requirements

**Recovery e-mail on the account**

- **FR-001**: Each account MUST be able to hold a recovery e-mail, stored trimmed and lowercased, and the moment it was confirmed. Accounts created before this feature hold none.
- **FR-002**: Registration with a password MUST require a valid recovery e-mail, typed once, with messages in Portuguese. It MUST NOT send or verify anything. Registration without it MUST be refused from the moment this is live, with no transition period.
- **FR-003**: The recovery e-mail MUST NOT be unique.
- **FR-004**: The profile MUST expose the recovery e-mail and whether it is confirmed, read-only.
- **FR-005**: Setting or changing the recovery e-mail MUST require the current password through the lockout-protected check, including the first time on an existing account. A wrong password is a form error and never signs the person out.
- **FR-006**: Changing the address MUST clear the confirmation and invalidate pending codes of the account. Sessions MUST be kept.
- **FR-007**: A signed-in person MUST be able to request a confirmation code, sent to the current recovery e-mail, and confirm the address with it.
- **FR-008**: Every signed-in recovery e-mail action MUST be refused for an account with no usable password.

**Recovery**

- **FR-009**: Anyone MUST be able to request recovery with only an e-mail address, and MUST always get the same success answer, whether or not anything matched and whether or not a limit was hit.
- **FR-010**: Matches MUST be active accounts with a usable password whose recovery e-mail equals the address, confirmed or not.
- **FR-011**: One message MUST go to the address, listing for each matching account its username and a separate code. Codes in one message MUST differ.
- **FR-012**: Anyone holding a valid code MUST be able to set a new password with the address, the code and the new password typed twice. The code identifies the account. The new password follows the existing rules and messages.
- **FR-013**: On success, in one transaction, the password MUST be set, every session of the account revoked and the code consumed. Afterwards the login lockout of that username MUST be cleared. No tokens are returned.
- **FR-014**: A wrong, expired or used code MUST give one single generic error.

**Code rules, for both purposes**

- **FR-015**: Codes MUST have 6 digits from a cryptographic source, be stored only as a keyed hash and never be logged.
- **FR-016**: Codes MUST be valid for 15 minutes, single use and allow at most 5 wrong attempts. A new request MUST invalidate earlier codes of the same purpose for that account.
- **FR-017**: For recovery, wrong attempts MUST count per e-mail address, so accounts sharing an address do not multiply the guesses.
- **FR-018**: Code requests MUST be limited to one per minute and five per hour per address, plus a per-client limit on the public request. The per-address limit counts every code sent to the address, of either purpose.
- **FR-019**: Expired codes and stale limit records MUST be removed by a periodic cleanup.

**Sending**

- **FR-020**: Sending MUST happen outside the request and only after the data is committed, so the response time does not reveal which addresses have accounts. Failures MUST be logged without the address.
- **FR-021**: Messages MUST be in Portuguese, plain and short, name the app and tell the person to ignore the message if they asked for nothing.
- **FR-022**: E-mail credentials MUST come from the environment only. Development MUST print messages to the console; tests MUST capture them.

**Security invariant**

- **FR-023**: A recovery e-mail MUST never be a login and MUST never identify an account for Google sign-in. Only Google writes the account's Google e-mail. This MUST be a rule of the constitution.
- **FR-024**: Addresses typed by anonymous callers that match nothing MUST NOT be stored in readable form.

### Key Entities

- **Recovery e-mail** (on the profile): the address and its confirmation moment. Never a login.
- **E-mail code**: a pending code of one account for one purpose (recovery or confirmation), tied to the address it was sent to, holding its hash, its expiry and the wrong-attempt count. At most one per account and purpose. Deleted with the account.
- **Send ledger**: the recent sending moments of one address, identified by a keyed hash of the address.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A person who forgot their password regains access in under 5 minutes with no help from a leader.
- **SC-002**: A caller cannot tell from the answer whether an address has an account: the answer is identical in every case, and the time of the request does not include the delivery of the message.
- **SC-003**: An attacker with one address gets at most 25 guesses per hour, across all accounts sharing it.
- **SC-004**: After a recovery, 100% of the sessions that existed before it stop working on their next use.
- **SC-005**: One address receives at most one message per minute and five per hour.
- **SC-006**: Every new password account can recover, because 100% of them hold an address from their first moment.
- **SC-007**: Google sign-in with an address typed by another person enters that person's account in 0 cases.

## Assumptions

- The app (separate spec, `TODO/specify_password_recovery_app.md`) is implemented after this one and reads this contract. Old app versions cannot register until they update, but keep signing in: the user's decision.
- Recovery works with an unconfirmed address, because the code itself proves access to the mailbox. Confirmation is optional and exists to catch typos while still signed in. For the same reason a recovery does not need to mark the address confirmed, and does not.
- Sharing the per-address send limit between the two purposes is the reading that protects the mailbox, which is what the limit is for.
- The volume is that of one church, so sending in a background thread without a queue is enough.
- Existing password accounts are not forced to add an address. The app's one-time notice needs nothing from the server beyond the profile fields.
- The provider (Brevo), the sender and the DNS records are already set up. Generating the SMTP key, storing it in the production environment and confirming the server reaches the SMTP port are done by the user before going live.
- Out of scope: e-mail as a login, any change to how Google sign-in finds accounts, a Google identity table, a unique e-mail constraint, verification at registration, notifying the old address on change, creating a password for a Google-only account, reset by a leader, SMS or WhatsApp codes.
