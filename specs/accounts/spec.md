# Accounts Domain Spec

Manages user identity, authentication, profile, password change, account deletion, member
access and access requests ("Perfis"). Single entry point for who the user is and how they prove it.

---

## Data Models

### User
- `id`: UUID (PK, auto-generated)
- `username`: string, max 150, unique, stored lowercase/trimmed, restricted charset (see Business Rules 2)
- `email`: string, unique (used by Google OAuth)
- `first_name`: string, max 30
- `last_name`: string, max 150
- `password`: hashed (unusable for Google-only users)
- Inherits from Django `AbstractUser`

### Profile
- `user`: OneToOne -> User (cascade delete)
- `name`: string, max 100, blank allowed (auto-filled from first_name + last_name on creation)
- `photo`: ImageField, nullable (stored at `profiles/{username}/{random}.{ext}`, where `ext`
  comes from the decoded image format and `{random}` is a `uuid4().hex`). Falls back to
  `profiles/{user_id}/` for legacy usernames that predate the charset rule. `photo_url`
  (`/ipbcb/media/profiles/...`) is readable only by members, through the authenticated media
  access check (`specs/009-protected-media-access/`); any member can read any profile photo,
  and the owner can always read their own, member or not.
  The random name is defence in depth, not collision avoidance: if an nginx edit ever
  re-published the media directory, a deterministic name would again let anyone fetch any
  member's photo from a URL built out of their username.
- `member_access`: bool, default false. The gate on member content (roll, birthdays, schedule,
  gallery, members-only events and media). Renamed from `is_member` by hand-written migration
  `accounts/0006` (`specs/022-access-requests` R-01). The **effective** access is this flag
  **or** an Admin/Liderança role (`core.domain.access.has_member_access`, permission
  `HasMemberAccess`); Mídia alone does not count. Set by approving an `access` request or in
  the Django admin; cleared by "revoke access".
- `access_requests_blocked`: bool, default false. Set by leaders in "Perfis"; a blocked
  account cannot create access requests.
- `member`: OneToOne -> `members.Member`, nullable, `SET_NULL`, `related_name="profile"`. Links
  the account to its record on the church roll, so the app can offer "photos of me" (gallery tag
  filter, `specs/015-gallery-member-tags/`). Unique: a member has at most one profile. Set and
  changed by leaders only: in the Django admin, whose profile form searches members by name
  (autocomplete), or with `PATCH api/admin/profiles/{user_id}/` (`specs/022-access-requests`);
  linking a member that already has a profile is refused and nothing is saved. Nothing links
  automatically. Deleting
  the member leaves the profile unlinked. Independent of `member_access`: neither sets, clears or
  checks the other.
- Roles (Admin, Liderança, Mídia) are **not** on the profile: they are the account's Django
  groups, assigned in the Django admin only. What each role can manage is in
  `specs/012-feature-role-permissions/`. The old `is_admin` flag was converted into the Admin
  role and removed there.

### AccessRequest (`specs/022-access-requests`)
- `user`: FK -> User, `CASCADE`, `related_name="access_requests"`
- `type`: `access` | `data_correction`
- `message`: text, nullable, ≤ 1000 characters after trim; required for `data_correction`
- `status`: `pending` | `approved` | `denied` (default `pending`). `approved` on a
  `data_correction` means "resolved"
- `decided_by`: FK -> User, nullable, `SET_NULL`; `decided_at`: datetime, nullable
- `denial_reason`: text, nullable, ≤ 500 characters after trim
- `created_at`: datetime
- At most one `pending` request per (user, type) — conditional unique constraint
- Read-only in the Django admin (decisions go through "Perfis", which also sets the flag and
  notifies)

### Signals (current behavior)
- **post_save User (created)**: auto-creates Profile with `name = "{first_name} {last_name}".strip().title()`
- **post_save User**: saves related profile on every user save
- **pre_save Profile**: deletes old photo file from disk when photo field changes
- **post_delete Profile**: deletes photo file from disk

---

## DTOs (Pydantic)

| DTO | Fields | Used by |
|-----|--------|---------|
| `RegisterDTO` | username, password, first_name, last_name | Register flow |
| `LoginDTO` | username, password | Login flow |
| `TokenDTO` | access, refresh (optional) | All auth responses |
| `PasswordChangeDTO` | current_password, new_password | Password change |
| `AccountDeletionDTO` | password (optional), id_token (optional) | Account deletion |

All inherit from `StrictBaseModel`. Username normalized (strip + lowercase) via field_validator.

---

## Endpoints

All under the base path `/ipbcb/` (e.g. `/ipbcb/api/auth/login/`).

### POST `api/auth/register/`
- **Public**, throttled (scope: `login`)
- Input: username, first_name, last_name, password, password_confirm
- Validation: username uniqueness, passwords match, min 6 chars
- Returns: `TokenDTO` (201)
- Flow: Serializer validates -> DTO -> UserRepository.create() -> JWT tokens

### POST `api/auth/login/`
- **Public**, throttled (scope: `login`) and under failed-attempt lockout
- Input: username, password
- Returns: `TokenDTO` (200), 401, or 429 once the `(username, address)` pair is locked
- Flow: DTO validates -> `django.contrib.auth.authenticate()` -> JWT tokens
- The view passes its `request` to `LoginService.login()`. This is the constitution's single
  named exception to "services never import HTTP objects" — `django-axes` cannot record or block
  an attempt it cannot attribute to a client. See `specs/008-login-brute-force-lockout/plan.md`.
- Five failures for the same `(normalised username, client address)` pair lock it for 30 minutes.
  A successful login resets the count; an attempt made during the lockout restarts the 30 minutes.
  Because the whole congregation shares one NAT address on the church WiFi, the pair — never the
  address alone — is what gets locked.

### POST `api/auth/google/`
- **Public**, throttled (scope: `login`)
- Input: `id_token` (Google OAuth2 ID token)
- Validates token against `GOOGLE_CLIENT_ID`
- Requires verified email
- Creates user if not exists (username from email prefix, collision-safe with counter suffix)
- Sets unusable password for Google-created users
- Downloads Google profile photo (400px, square crop) on first login if profile has no photo
- Returns: `TokenDTO` (200) or 400/401

### POST `api/auth/refresh/`
- **Public** — the refresh token is the proof. `RefreshAPI` + `RefreshService`, not
  SimpleJWT's `TokenRefreshView`
- Input: refresh token
- Returns: a new access **and** refresh token (rotation), or 401
- The pair is rebuilt from the user record, never by copying the presented token's claims
  — see Business Rule 15 for why
- The presented token is blacklisted: rotation stays single use
- An inactive user cannot refresh, otherwise the endpoint mints a token
  `JWTAuthentication` rejects on the next request

### POST `api/auth/logout/`
- **Public** (SimpleJWT built-in `TokenBlacklistView`) — the refresh token is the proof
- Input: refresh token
- Blacklists it, so it can no longer be exchanged for an access token
- Returns: 200 empty, or 401 when the token is invalid or already blacklisted
- The access token stays valid until it expires (up to 60 min). Revoking it per request
  would mean a database read on every call, which is the cost JWT exists to avoid.

### GET `api/me/profile/`
- **Authenticated**
- Returns: name, is_member, member_access, access_status, access_requests_blocked,
  data_correction_pending, photo_url, `roles` (`[{id, name}]`), `permissions` (every
  scope as a key, level `view`/`manage`/`owner` or `null`) and `member_id` (the linked member's
  id, or `null`). Shape in `specs/012-feature-role-permissions/contracts/profile-api.md`;
  `member_id` added by `specs/015-gallery-member-tags/`
- Supports ETag (`If-None-Match` -> 304)
- Auto-creates Profile if missing (get_or_create)

- Also returns `is_worship_member` (the linked member belongs to the ministry named "Louvor") and
  `can_save_setlist` (`is_worship_member` and `manage` on `songs`), computed on every read; the
  ETag changes with them (`specs/017-sunday-setlist-push/`)
- Also returns `username`, `has_password` (`user.has_usable_password()` — the **account's**
  password, never how this session signed in) and `date_joined` (`"YYYY-MM-DD"`, the account's
  creation date in `America/Sao_Paulo`) (`specs/021-user-account/`)
- Also returns (`specs/022-access-requests/`): `member_access` — the **effective** access (flag
  or Admin/Liderança role); `is_member` — same value, deprecated, kept for at least two app
  versions; `access_status` — `granted` | `pending` (an `access` request is pending) | `none`;
  `access_requests_blocked`; `data_correction_pending`. Roll data is **never** here: the app
  writes this response to disk, so the account's roll record is served by
  `GET api/me/member/` (members domain)

### PATCH `api/me/profile/`
- **Authenticated**
- Updatable: `name` only (is_member, member_access, access_status, access_requests_blocked,
  data_correction_pending, photo_url, roles, permissions, member_id,
  is_worship_member, can_save_setlist, username, has_password, date_joined are read-only; a
  value sent for them is ignored)
- `name`: trimmed; blank or whitespace-only → 400 ("Este campo não pode ficar em branco.");
  more than 100 characters → 400 ("O nome pode ter no máximo 100 caracteres.")
- Returns: updated profile (200)

### POST `api/me/profile/photo/`
- **Authenticated**
- Input: multipart photo file
- Validated by decoded content via `core.files.image_validation`: max 10 MB, and the
  file must decode as JPEG, PNG, WEBP or GIF. SVG is rejected — Pillow cannot decode it,
  and it is a scriptable document.
- The stored extension comes from the detected format, never from the uploaded filename
- Validation runs **before** the old photo is deleted, so a rejected upload leaves the
  existing photo intact
- The file is streamed to storage; it is never fully read into memory
- Returns: detail message + photo_url (200), or 400 with `VALIDATION_ERROR`

### DELETE `api/me/profile/photo/`
- **Authenticated**
- Removes photo from profile and disk
- Returns: 204

---

### POST `api/me/password/`
- **Authenticated**, throttled (scope: `login`), under failed-attempt lockout
- Input: `current_password`, `new_password`, `new_password_confirm` — the new password follows
  the registration rule (≥ 6 characters, confirmation equal), same messages
- Only for an account with a usable password; otherwise 409 `PASSWORD_NOT_SET`
- Wrong current password: 400 `INVALID_PASSWORD` (never 401 — the session is still valid)
- On success every refresh token of the account is blacklisted and every access token issued
  before stops working (`CHECK_REVOKE_TOKEN`), **the caller's included**; the response is a new
  pair (`TokenDTO`, 200) built from the user after the change. The app must switch to it.
- Contract: `specs/021-user-account/contracts/account-api.md`

### POST `api/me/delete/`
- **Authenticated**, throttled (scope: `login`); `POST` because the secret travels in the body
- Input: `{"password"}` for an account with a password, `{"id_token"}` (fresh Google token) for
  one without. The other field is ignored; the missing one is a 400 naming the method
- A Google token confirms only if it passes sign-in's verification and resolves, through the
  same `get_by_email` lookup, to **this** account (403 `GOOGLE_ACCOUNT_MISMATCH` otherwise; a
  token failing verification is 400 `INVALID_GOOGLE_TOKEN`)
- Superusers: 409 `ACCOUNT_DELETION_BLOCKED`, checked first. The Admin role does not block
- Immediate, in one transaction: refresh tokens blacklisted, then the user deleted. Returns 204

### GET/POST `conta/excluir/` (web page)
- **Public** HTML page in pt-BR, the Play Store's "delete account" link
  (`/ipbcb/conta/excluir/` in production). The constitution's one exception to "no web frontend"
- Plain Django view: CSRF by the middleware, `never_cache`, input through DRF serializers,
  POST throttled with the `login` budget per client address
- `method=password`: username + password + confirmation; the sign-in counts against the
  lockout. A wrong username or password gets one generic message. Locked out → 429 page
- `method=google`: the Google Identity Services button (client `GOOGLE_CLIENT_ID`, shown only
  when it is set) hands a credential to the form. Only for accounts without a password; an
  account with one is told to use username and password
- Same effects as `api/me/delete/`; superusers are refused
- Sets `Cross-Origin-Opener-Policy: same-origin-allow-popups` and `Referrer-Policy:
  strict-origin-when-cross-origin`, which the Google button needs

### What deleting an account removes and keeps

| Reference | On deletion |
|-----------|-------------|
| `Profile` (and its photo file, by the `post_delete` signal) | deleted |
| `core.DeviceToken` | deleted |
| groups / user permissions links | deleted |
| Django admin `LogEntry` | deleted (cascade; accepted — superusers cannot delete themselves) |
| SimpleJWT `OutstandingToken` | kept without owner, blacklisted first |
| gallery `Photo.uploaded_by`, `PhotoTag.tagged_by`, `TrashEntry.deleted_by`; events `Event.created_by`, `Event.updated_by`; members `MemberChangeLog.editor`; songs `Setlist.saved_by`, `HymnalViewEvent.user` | kept, author cleared (`SET_NULL`) |
| `members.Member` linked by `Profile.member` | kept untouched; only the link goes |
| `AccessRequest.user` | deleted (cascade) |
| `AccessRequest.decided_by` | kept, decider cleared (`SET_NULL`) |

A new FK to the user must choose explicitly between these behaviours and be added here.

---

### POST `api/me/access-requests/`
- **Authenticated**. Body `{"type": "access" | "data_correction", "message"?}` → `201` with the
  request (`id, type, message, status, created_at, decided_by, decided_at, denial_reason`)
- Refusals, in this order: blocked → 403 `ACCESS_REQUESTS_BLOCKED` ("Pedidos de acesso
  indisponíveis. Fale com a liderança."); `access` with effective access → 409
  `MEMBER_ACCESS_ALREADY_GRANTED`; same type pending → 409 `ACCESS_REQUEST_PENDING`; any request
  in the last rolling 24 h (any type, any status) → 429 `ACCESS_REQUEST_RATE_LIMITED` with
  `retry_after_seconds`. The 24 h rule reads the table, it is not a DRF throttle
- Push `access_request_created` (`request_id`, `request_type`) to every active account with
  `manage` on `profiles`, except the requester

### "Perfis" — `api/admin/profiles/…` (scope `profiles`)
- Admin `owner`, Liderança `manage`, Mídia none. GET `view`, POST/PATCH `manage`
- `GET api/admin/profiles/?status=pending|all` → `{"accounts": [...]}`: `pending` = accounts with
  a pending request, oldest pending first; `all` (default) = every active account by name. Each
  account: `id, name, username, photo_url, member_access` (the **stored** flag),
  `access_via_role, access_requests_blocked, member {id, name} | null, date_joined,
  pending_requests`. Never the e-mail
- `GET api/admin/profiles/{user_id}/` → the account plus `requests` (history, newest first)
- `PATCH api/admin/profiles/{user_id}/` `{access_requests_blocked?, member_id?}` — block/unblock,
  link/unlink the roll (unknown member 400 on `member_id`; member linked elsewhere 409
  `MEMBER_ALREADY_LINKED`; unknown fields 400). No push
- `POST api/admin/profiles/{user_id}/revoke-access/` — clears the flag. No push
- `POST api/admin/profiles/requests/{id}/approve/` — `access`: sets the flag; `data_correction`:
  only closes it. Push `access_request_approved` to the requester
- `POST api/admin/profiles/requests/{id}/deny/` `{reason?}` (≤ 500) — push
  `access_request_denied` with `reason` when given
- Deciding a request that is not pending → 409 `ACCESS_REQUEST_NOT_PENDING`; unknown → 404.
  Every write answers the account detail
- Contract: `specs/022-access-requests/contracts/access-api.md`

---

### POST `api/me/devices/`
- **Authenticated**
- Input: `{"token": "<FCM registration token>"}` — string, trimmed, 1-512 chars, no inner
  whitespace
- Stores the token as `core.DeviceToken` for the caller. Idempotent; a token already registered
  by another account moves to the caller (one phone, one owner: the account last signed in)
- Returns: 204, or 400 `VALIDATION_ERROR`
- The app calls it after every login and whenever FCM rotates the token

### POST `api/me/devices/unregister/`
- **Authenticated** — the app calls it on logout, **before** `api/auth/logout/`
- Input: `{"token": "..."}`
- Deletes the token only if the caller owns it. Unknown token or someone else's: nothing
  changes, still 204, so logout never fails on it
- `POST`, not `DELETE` on a path: the token must never appear in a URL (access logs)

Tokens are also deleted when FCM reports them unregistered, and with their user (`CASCADE`).
Never logged, never shown in the Django admin. Contract in
`specs/017-sunday-setlist-push/contracts/me-api.md`.

---

## Business Rules

1. Username is always stored lowercase and trimmed
2. Username matches `^[a-z0-9]([a-z0-9._-]*[a-z0-9])?$` — ASCII lowercase, digits, dot,
   hyphen and underscore, starting and ending alphanumeric. Narrower than Django's
   `UnicodeUsernameValidator`, which accepts `..` and every Unicode letter: the username
   is also a directory name under MEDIA_ROOT, and Unicode letters allow homoglyph
   impersonation. Validation runs **after** normalisation.
3. Username must be unique (checked at serializer level)
4. No password complexity requirements — any password >= 6 chars accepted
5. Google users get unusable password — cannot login via username/password
6. Google photo only downloaded on first login when profile has no photo yet
7. Google username collision resolved by appending incrementing counter (e.g., `john`, `john1`, `john2`)
7a. The Google username base is derived from the e-mail local part, which never passes
    through `RegisterSerializer` — it is sanitised (accents transliterated, invalid
    characters replaced with `-`) so it satisfies rule 2
7b. The Google avatar is remote, untrusted content: it goes through the same image
    validation as a user upload. A rejected avatar is logged and never blocks the login
8. Profile auto-created on user creation (via signal) and on profile access (via get_or_create)
9. Old profile photos deleted from filesystem when replaced or profile deleted
10. All auth endpoints share `login` throttle scope — password change, account deletion and the
    deletion web page included
10b. Every rule about passwords looks at the **account** (`has_usable_password()`), never at
     how the session signed in: Google sign-in also enters an account that has a password
10c. Account deletion is immediate, with no grace period and no recovery
10a. Deactivation is `User.is_active` only. SimpleJWT checks it on every authenticated
     request (`CHECK_USER_IS_ACTIVE`), so it covers endpoints guarded by plain
     `IsAuthenticated` as well — which a permission class could not. `Profile.active`
     used to exist alongside it and was read by nothing: setting it revoked no access,
     while looking like it did. Removed in migration
     `accounts/0002_remove_profile_active.py`
11. Username/password login is additionally under failed-attempt lockout (`django-axes`),
    keyed on the `(normalised username, client address)` pair. The normalisation applied to
    the lockout key is the same `strip().lower()` the DTOs apply — otherwise `admin`, `Admin`
    and `ADMIN` would each get their own budget of failures. Google login is unaffected: it
    never reaches `authenticate()`
12. Three levers revoke a token, in increasing severity:
    - `POST api/auth/logout/` blacklists one refresh token (leaving the app on a device)
    - Changing the user's password revokes **every** token that user holds, on every
      device, access tokens included and immediately (`CHECK_REVOKE_TOKEN`, which puts a
      hash of the password in each token and checks it per request). This is the answer
      to a lost or stolen device. `CHECK_REVOKE_TOKEN` only runs when an access token
      authenticates, and refresh rebuilds from the user, so `api/me/password/` also
      blacklists every refresh token (`RefreshTokenRepository.revoke_all`). A password
      changed in the Django admin blacklists nothing, so an old refresh token can still
      mint a working pair — open item in `tasks.md`
    - `User.is_active = False` blocks the account entirely (`CHECK_USER_IS_ACTIVE`,
      on by default)
13. Enabling `CHECK_REVOKE_TOKEN` invalidates every access token issued before it: those
    carry no `hash_password` claim, so the check fails. Nobody has to sign in again — the
    client's next refresh rebuilds the pair from the user record (rule 15) and the claim
    appears. This only holds because `api/auth/refresh/` rebuilds rather than copies
14. `BLACKLIST_AFTER_ROTATION` writes a row per refresh. The `ipbcb_token_flush` service
    in `compose.prod.yml` runs `manage.py flushexpiredtokens` daily so the table does not
    grow without bound. Housekeeping, not security — an expired token is refused anyway
15. Any endpoint issuing tokens builds them from the user, through
    `features.accounts.auth.jwt.get_tokens_for_user`. Deriving a token from another token
    freezes whatever claims existed when the first was minted, and the mismatch is silent:
    a 200 carrying credentials that fail on the very next request. A client that only
    signs out when the *refresh* fails is then stuck with no route back to the login screen

---

15a. Member access is decided in one place, `core.domain.access.has_member_access(flag, roles)`:
     the flag or an Admin/Liderança role. A role never requires it and it never grants a level.
     No e-mail is read, shown or accepted by any access-request or "Perfis" endpoint (Google
     sign-in links accounts by e-mail)

---

## Errors

| Situation | Status | Message |
|-----------|--------|---------|
| Missing id_token | 400 | "id_token e obrigatorio." |
| Invalid Google token | 401 | "Token do Google invalido." |
| Unverified Google email | 400 | "Conta Google sem email verificado." |
| Google user creation clash (unique e-mail or username) | 500 | "Erro ao criar usuario." |
| Invalid credentials (login) | 401 | "Nome de usuario ou senha invalidos." |
| Too many failed logins (login, admin) | 429 | "Muitas tentativas de login. Tente novamente em 30 minutos." (`ACCOUNT_LOCKED`, with `cooloff_seconds`) |
| Username taken (register) | 400 | Validation error on username field |
| Username taken between the check and the insert (register race) | 409 | `UsernameAlreadyExistsError` |
| Passwords don't match | 400 | Validation error on password_confirm field |
| No file in photo upload | 400 | "Nenhuma foto enviada." |
| Blank or > 100-character name (profile PATCH) | 400 | `VALIDATION_ERROR` on `name` |
| Wrong password confirming a change or a deletion | 400 | `INVALID_PASSWORD` "Senha incorreta." |
| Password change on an account without password | 409 | `PASSWORD_NOT_SET` "Esta conta não tem senha." |
| Deletion without the confirmation this account uses | 400 | `VALIDATION_ERROR` "Esta conta tem senha: confirme com a senha." / "Esta conta não tem senha: confirme com o Google." |
| Google confirmation token fails verification | 400 | `INVALID_GOOGLE_TOKEN` |
| Google confirmation token of another account (or none) | 403 | `GOOGLE_ACCOUNT_MISMATCH` |
| Superuser asks for deletion | 409 | `ACCOUNT_DELETION_BLOCKED` |
| Access request while blocked | 403 | `ACCESS_REQUESTS_BLOCKED` |
| `access` request with access already | 409 | `MEMBER_ACCESS_ALREADY_GRANTED` |
| Same type already pending | 409 | `ACCESS_REQUEST_PENDING` |
| Second request inside 24 h | 429 | `ACCESS_REQUEST_RATE_LIMITED` (+ `retry_after_seconds`) |
| `data_correction` without message | 400 | `VALIDATION_ERROR` on `message` |
| Deciding a decided request | 409 | `ACCESS_REQUEST_NOT_PENDING` |
| Linking a member linked elsewhere | 409 | `MEMBER_ALREADY_LINKED` |
| Linking an unknown member | 400 | `VALIDATION_ERROR` on `member_id` |
| Unknown `status` filter on "Perfis" | 400 | `VALIDATION_ERROR` on `status` |

A missing profile is never an error: every profile read and write goes through
`get_or_create`, so there is no "profile not found" exception.

---

## Architecture

```
RegisterAPI        -> RegisterService    -> UserRepository
LoginAPI           -> LoginService       -> django.contrib.auth.authenticate (+ django-axes)
RefreshAPI         -> RefreshService     -> UserRepository
GoogleLoginAPI     -> GoogleAuthService  -> UserRepository, ProfileRepository
MeProfileAPIView   -> ProfileService     -> ProfileRepository
                   -> AccessService, WorshipAccessService (core) for roles and worship flags
ProfilePhotoAPIView -> ProfileService    -> ProfileRepository
DeviceToken*APIView -> DeviceTokenService (core)
PasswordChangeAPIView -> PasswordChangeService -> UserRepository, RefreshTokenRepository
                      -> LoginService.verify_password (as a PasswordCheck)
AccountDeletionAPIView -> AccountDeletionService -> UserRepository, RefreshTokenRepository,
                                                    GoogleAuthService.resolve_existing_account
                       -> LoginService.verify_password (as a PasswordCheck)
AccountDeletionPageView -> LoginService.authenticate_credentials, AccountDeletionService
MeAccessRequestAPIView -> AccessRequestService -> AccessRequestRepository,
                         ManagedAccountRepository, AccessService, PushService (core)
AdminProfile*APIView / AdminAccessRequest*APIView -> ProfileManagementService
                         -> AccessRequestRepository, ManagedAccountRepository, PushService
MeProfileAPIView      -> AccessRequestService.access_state (member-access fields)
```

- Password checks: `LoginService` is the only place that calls `authenticate()`, so every check
  is under django-axes. `PasswordChangeService` and `AccountDeletionService` receive a
  `PasswordCheck` callable from the view and decide when it runs (a Google-only account or a
  superuser is refused before any password is checked).
- Account exceptions in `core/domain/account_exceptions.py`, DTOs in
  `core/application/dtos/account_dtos.py`.
- The web page renders its own lockout message and marks the response with
  `core.http.lockout.mark_renders_own_lockout`, so `AxesMiddleware` does not swap it for JSON.

- Repositories: `UserRepository` and `ProfileRepository` (Protocols in
  `repositories/interfaces.py`, ORM implementations next to them). The only ORM access.
- `MeProfileAPIView.patch`: `ProfileSerializer` only validates; the write is
  `ProfileService.update_profile()`. Read-only fields never reach it.
- Google avatar: `AvatarDownloader` (Protocol) <- `HttpAvatarDownloader`
  (`repositories/avatar_downloader.py`, the only `requests` import in accounts, 5 s timeout).
  Returns the bytes or `None`; a failure logs `avatar_download_failed` with the reason, never
  the URL.
- Google user creation: `UserRepositoryImpl.create_google_user` runs in one transaction and
  turns an `IntegrityError` (two first logins racing for the same e-mail or username) into
  `GoogleUserCreationError` (500), chained to the original. Any other error propagates as
  itself.
- Tokens: `features/accounts/auth/jwt.py` (`get_tokens_for_user`), see Business Rule 15.
- Google token data goes through `GoogleUserDTO`; register and login through `RegisterDTO` and
  `LoginDTO`.
- Everything wired in `config/di.py`. Domain errors from `core/domain/exceptions.py`, mapped
  to HTTP by the project's exception handler.

### Known deviations

1. **Username uniqueness in the serializer.** `RegisterSerializer.validate_username()` queries
   `User.objects` so a taken username is a field-level 400. Kept on purpose; `RegisterService`
   re-checks and raises `UsernameAlreadyExistsError` (409) for the race.
2. **`LoginService` receives the `HttpRequest`.** The constitution's one named exception, see
   `POST api/auth/login/`; widened to `authenticate_credentials()` and `verify_password()` by
   `specs/021-user-account` R-01.
