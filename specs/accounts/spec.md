# Accounts Domain Spec

Manages user identity, authentication, and profile. Single entry point for who the user is and how they prove it.

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
- `is_member`: bool, default false
- Roles (Admin, Liderança, Mídia) are **not** on the profile: they are the account's Django
  groups, assigned in the Django admin only. What each role can manage is in
  `specs/012-feature-role-permissions/`. The old `is_admin` flag was converted into the Admin
  role and removed there.

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

All inherit from `StrictBaseModel`. Username normalized (strip + lowercase) via field_validator.

---

## Endpoints

All under `/ipbcb/accounts/`.

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
- Returns: name, is_member, photo_url, `roles` (`[{id, name}]`) and `permissions` (every
  scope as a key, level `view`/`manage`/`owner` or `null`). Shape in
  `specs/012-feature-role-permissions/contracts/profile-api.md`
- Supports ETag (`If-None-Match` -> 304)
- Auto-creates Profile if missing (get_or_create)

### PATCH `api/me/profile/`
- **Authenticated**
- Updatable: `name` only (is_member, photo_url, roles, permissions are read-only)
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
10. All auth endpoints share `login` throttle scope
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
      to a lost or stolen device
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

## Errors

| Situation | Status | Message |
|-----------|--------|---------|
| Missing id_token | 400 | "id_token e obrigatorio." |
| Invalid Google token | 401 | "Token do Google invalido." |
| Unverified Google email | 400 | "Conta Google sem email verificado." |
| Google user creation failure | 500 | "Erro ao criar usuario." |
| Invalid credentials (login) | 401 | "Nome de usuario ou senha invalidos." |
| Too many failed logins (login, admin) | 429 | "Muitas tentativas de login. Tente novamente em 30 minutos." (`ACCOUNT_LOCKED`, with `cooloff_seconds`) |
| Username taken (register) | 400 | Validation error on username field |
| Passwords don't match | 400 | Validation error on password_confirm field |
| Profile not found (photo delete) | 404 | "Perfil nao encontrado." |

---

## Architecture (current state)

```
Views (auth.py, profile.py)
  |
  +---> Serializers (validation + DTO creation)
  |
  +---> UserRepository (only used by RegisterAPI)
  |
  +---> Models directly (GoogleLoginAPI, ProfileViews bypass repository)
```

### Known violations against constitution.md

1. **No service layer** — Views contain business logic directly
2. **Views access ORM** — GoogleLoginAPI uses `User.objects` directly; profile views use `Profile.objects`
3. **DI partial** — Only RegisterAPI injects UserRepository; GoogleLoginAPI bypasses it
4. **No Google auth DTO** — Google token data extracted as raw dict values, no Pydantic validation
5. **Repository incomplete** — Missing `get_by_email()`, `username_exists()`, `get_or_create_profile()`
6. **Broad exception catch** — `except Exception:` in GoogleLoginAPI hides root cause
7. **Serializer touches ORM** — `RegisterSerializer.validate_username()` queries `User.objects` directly

### Target architecture

```
Views (thin HTTP layer)
  |
  +---> Serializers (I/O validation only, no ORM)
  |
  +---> Services (business logic, orchestration)
  |       +---> RegisterService
  |       +---> LoginService
  |       +---> GoogleAuthService
  |       +---> ProfileService
  |
  +---> Repositories (ORM access)
          +---> UserRepository (complete: create, get_by_email, username_exists, etc.)
          +---> ProfileRepository (get_or_create, update_photo, delete_photo)
```

All services injected via `config/di.py`. Domain errors as exceptions from `core/domain/exceptions.py`.
