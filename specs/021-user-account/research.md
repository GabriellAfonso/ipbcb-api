# Research: User Account

Decisions taken while planning. Points settled with the app session are marked _(agreed)_; the
rest follow from the code and the constitution.

## R-01 — Password re-checks go through `LoginService` with the request _(agreed)_

**Decision**: `LoginService` gains `authenticate_credentials(dto, request) -> User` (the part of
`login()` that calls `django.contrib.auth.authenticate`, which `login()` now reuses) and
`verify_password(user, password, request) -> None` (calls the former with the user's own
username, checks the result is the same account, raises `InvalidPasswordError`). The constitution's
named exception widens from `LoginService.login()` to these `LoginService` methods.

**Rationale**: the constitution requires every password check to be under django-axes, and
axes needs the `HttpRequest` (008 D-1). Keeping every request-taking method on the one class
already named as the exception keeps the exception a single place to audit.

**Alternatives rejected**: `user.check_password()` in a service — no lockout, breaks the
constitution. A `PasswordVerifier` port built per request in the container — cleaner on paper,
but the library's handler still wants the real request, so the port would only move the same
dependency one level down (same argument as 008 D-1).

## R-02 — Services own the order of checks; HTTP stays in the view

**Decision**: `PasswordChangeService.change_password(user, dto, verify_password)` and
`AccountDeletionService.delete_confirmed(user, dto, verify_password)` take a
`PasswordCheck = Callable[[str], None]`. The view builds it as
`lambda raw: login_service.verify_password(user, raw, request._request)`.

**Rationale**: the order matters and is business logic — a Google-only account must get
`PASSWORD_NOT_SET` / the "confirm with Google" error **before** any password is checked, and a
superuser must be refused before anything is touched. Passing a callable keeps that order in
the service while the service never sees an HTTP object.

## R-03 — Revoking sessions: blacklist every outstanding refresh token _(agreed)_

**Decision**: new `RefreshTokenRepository.revoke_all(user_id)` blacklists every
`OutstandingToken` of the user that is not blacklisted yet (`bulk_create(ignore_conflicts=True)`).
Password change: set password → revoke all → issue a new pair from the user (Business Rule 15).
Deletion: revoke all → delete the user, one transaction.

**Rationale**: `CHECK_REVOKE_TOKEN` already kills every access token issued before a password
change (their `hash_password` claim no longer matches), including the caller's. It does **not**
stop old refresh tokens: `RefreshService` rebuilds from the user and SimpleJWT checks the claim
only in `JWTAuthentication`. Blacklisting closes that. The caller keeps working with the pair
returned in the response, minted after the change.

On deletion the access tokens die because their user no longer exists; the refresh tokens would
be refused for the same reason (`RefreshService` finds no user), and are blacklisted anyway so
the record is explicit. `OutstandingToken.user` is `SET_NULL` in SimpleJWT 5.5.1, so the rows
survive without owner and `flushexpiredtokens` cleans them later.

## R-04 — Google confirmation reuses sign-in verification _(agreed)_

**Decision**: `GoogleAuthService.resolve_existing_account(id_token) -> User | None` verifies
the token exactly like sign-in (`_verify_token`: signature, audience `GOOGLE_CLIENT_ID`, expiry,
verified e-mail) and looks the account up with the same `get_by_email`. It never creates a user
nor touches the photo. `AccountDeletionService` compares the result's **primary key** with the
caller's; a different account or none → `GOOGLE_ACCOUNT_MISMATCH`.
`InvalidGoogleTokenError` / `UnverifiedGoogleEmailError` (401/400 at sign-in) are translated into
`InvalidGoogleConfirmationError` (`400 INVALID_GOOGLE_TOKEN`), so the app never reads a failed
confirmation as an expired session.

## R-05 — Confirmation method follows the account _(agreed)_

**Decision**: `has_usable_password()` decides. With a password: `password` is required,
`id_token` is ignored. Without: `id_token` is required, `password` ignored. A missing required
field → `400 VALIDATION_ERROR` whose `detail` says which method this account uses.

## R-06 — Superusers cannot delete themselves _(agreed)_

**Decision**: `AccountDeletionService` raises `AccountDeletionBlockedError`
(`409 ACCOUNT_DELETION_BLOCKED`) for `is_superuser`, before any confirmation is checked (API) or
right after sign-in (web page). The Admin **role** is a group and does not block.

## R-07 — References to the user: no migration _(agreed)_

**Decision**: every FK to the user already has the wanted behaviour (table in spec.md). Profile
photo file goes through the existing `post_delete` signal on `Profile`, which Django sends for
cascaded rows. Device tokens cascade. No schema change.

## R-08 — Web page: plain Django view, DRF serializers, Django CSRF

**Decision**: `features/accounts/views/account_deletion_page.py`, a plain Django class view
(`View`), so `CsrfViewMiddleware` protects it natively (DRF `APIView` is CSRF-exempt unless
session auth runs). Input still goes through DRF serializers (constitution: Data Integrity).
Templates under `features/accounts/templates/accounts/`. `never_cache` (the page carries a CSRF
token). The form action comes from `{% url %}`, so `FORCE_SCRIPT_NAME` puts `/ipbcb/` in front —
nothing hardcoded.

**Throttle**: DRF throttles do not run on a plain view, so the view calls a small
`AccountDeletionPageThrottle(SimpleRateThrottle)` on POST: scope `login` (same budget as the auth
endpoints), keyed by `get_ident`, which honours `NUM_PROXIES` like every other throttle
(constitution: Client IP). Over the limit → the page with status 429.

**Lockout rendering**: `AxesMiddleware` replaces the response of a locked-out request with
`AXES_LOCKOUT_CALLABLE`'s JSON. The page renders its own Portuguese lockout message (status 429)
and marks the response with `core.http.lockout.mark_renders_own_lockout`; the callable returns a
marked response unchanged. `core` stays unaware of the page; the admin and the API keep the
current JSON.

## R-09 — Google button on the web page _(agreed)_

**Decision**: Google Identity Services (`https://accounts.google.com/gsi/client`), popup/callback
mode, with the existing `GOOGLE_CLIENT_ID` (a Web-type client — the app's server client ID). The
callback copies the credential into a hidden field of a second form that carries the Django CSRF
token and the confirmation checkbox. Redirect mode was rejected: it posts with Google's own
double-submit cookie, which Django's CSRF check would refuse.

The page overrides two headers Django's `SecurityMiddleware` sets by default (it uses
`setdefault`, so a view's own value wins): `Cross-Origin-Opener-Policy:
same-origin-allow-popups` (the popup must talk back to the page) and `Referrer-Policy:
strict-origin-when-cross-origin` (GIS refuses to render without the origin in the referrer).
When `GOOGLE_CLIENT_ID` is empty (dev), the Google section is not rendered.

**Manual step** (outside code): Google Cloud Console → the OAuth client → "Authorized
JavaScript origins" → add `https://<domain>`.

## R-10 — Profile fields

**Decision**: `ProfileSerializer` gains read-only `username`, `has_password`
(`user.has_usable_password()`) and `date_joined` (`localtime(user.date_joined)` in
`America/Sao_Paulo`, ISO date). `name` gets `allow_blank=False` (DRF already trims, so a
whitespace-only name becomes blank and is refused) and pt-BR messages; `max_length=100` comes
from the model. Today a blank name is accepted (model `blank=True`) — that is the fix.

## R-11 — Shared password field rules

**Decision**: the 6-character rule and its messages move to one factory in the serializers
module, used by `RegisterSerializer` and `PasswordChangeSerializer` alike, so the two cannot
drift (CLAUDE.md: no duplication).

## R-12 — Exceptions in their own module

**Decision**: `core/domain/account_exceptions.py`, re-exported by `core/domain/exceptions.py`
(the 500-line rule, same pattern as `event_exceptions.py`). Messages pt-BR: the app shows
`detail` as is.
