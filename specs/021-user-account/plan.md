# Implementation Plan: User Account

**Branch**: `021-user-account` | **Date**: 2026-10-21 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/021-user-account/spec.md`

## Summary

All inside `features/accounts`, plus exceptions and DTOs in `core`. The profile serializer gains
three read-only fields and a non-blank `name`. Two new endpoints — `POST api/me/password/` and
`POST api/me/delete/` — and one public HTML page, `conta/excluir/`. Password checks go through a
new `LoginService.verify_password()` / `authenticate_credentials()` so they stay under django-axes
(R-01, constitution amendment). Sessions are revoked by blacklisting every outstanding refresh
token of the user (R-03); the password change answers with a fresh pair. Deletion is a single
transaction — blacklist, then delete the user — and the existing cascades and `SET_NULL`s do the
rest (R-07). No migration.

## Technical Context

**Language/Version**: Python 3.14, Django 6.0.8

**Primary Dependencies**: DRF, SimpleJWT 5.5.1 (`token_blacklist`), django-axes 8.3.1,
google-auth, Pydantic 2, `dependency-injector`. Browser side: Google Identity Services script.
No new Python dependency

**Storage**: PostgreSQL (prod), SQLite (tests); profile photos on default storage

**Testing**: pytest + pytest-django from `server/`; unit tests with named fakes
(`features/accounts/tests/fakes.py`), integration through `APIClient` / Django `Client`
(`enforce_csrf_checks=True` for the page)

**Target Platform**: Linux container behind nginx at `/ipbcb/`

**Project Type**: web service (REST API for the Android app) + one server-rendered page

**Performance Goals**: deletion = a handful of statements in one transaction; profile read adds
no query beyond the user already loaded

**Constraints**: functions 4–20 lines, files < 500 lines, no cross-feature imports, no `.raw()`,
canonical error shape, pt-BR user-facing text

**Scale/Scope**: hundreds of accounts; 2 endpoints, 1 page, 3 profile fields

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Rule | How this plan complies |
|------|------------------------|
| `IsAuthenticated` on protected views; public only when declared | Password/delete views `IsAuthenticated`. The web page is public by nature (the person is not signed in) — declared in spec FR-016 and in the constitution amendment below |
| Every password check behind django-axes | `LoginService.verify_password` / `authenticate_credentials` call `authenticate(request=…)`; same `(username, address)` key |
| Services never import HTTP objects (one named exception) | **Amendment**: the exception is widened from `LoginService.login()` to `LoginService`'s three request-taking methods (R-01). Other services receive a `PasswordCheck` callable (R-02) |
| Input validated by DRF serializers | `PasswordChangeSerializer`, `AccountDeletionSerializer`, two web serializers; `require_object_body` before them |
| Repositories only touch the ORM | `UserRepository.set_password/delete`, new `RefreshTokenRepository` |
| Features never import each other | Only `features.accounts` and `core` |
| DI container, Pydantic DTOs | New providers in `config/di.py`; `account_dtos.py` |
| Error shape `{error_code, detail}` | Domain exceptions with their own `error_code` (data-model.md) |
| Caching | Profile keeps `private, no-store`; the page is `never_cache` |
| Client IP via ipware / `NUM_PROXIES` | Page throttle uses DRF `get_ident` (R-08) |
| Single client: Android app, no web frontend | **Amendment**: one exception, the account-deletion page required by Google Play (Complexity Tracking) |
| Migrations | None (`makemigrations --check`) |
| Specs and code in the same commit | 021 spec/plan/tasks, `specs/accounts/spec.md`, constitution, `docs/features/accounts.md` |

**Gate**: PASS with two justified amendments (Complexity Tracking). Re-checked after Phase 1:
PASS.

## Project Structure

### Documentation (this feature)

```text
specs/021-user-account/
├── spec.md
├── plan.md              # this file
├── research.md          # R-01 … R-12
├── data-model.md
├── quickstart.md
├── contracts/
│   └── account-api.md   # the contract the app builds against
├── checklists/
│   └── requirements.md
└── tasks.md             # /speckit-tasks
```

### Source Code

```text
server/
├── config/di.py                                   # + refresh_token_repository, password_change_service,
│                                                  #   account_deletion_service; wiring of the new views
├── core/
│   ├── application/dtos/account_dtos.py           # PasswordChangeDTO, AccountDeletionDTO
│   ├── domain/account_exceptions.py               # R-12; re-exported by exceptions.py
│   └── http/lockout.py                            # + mark_renders_own_lockout (R-08)
└── features/accounts/
    ├── repositories/
    │   ├── interfaces.py                          # + set_password, delete; RefreshTokenRepository
    │   ├── user_repository.py
    │   └── refresh_token_repository.py            # new
    ├── services/
    │   ├── login_service.py                       # + authenticate_credentials, verify_password
    │   ├── google_auth_service.py                 # + resolve_existing_account
    │   ├── password_change_service.py             # new
    │   └── account_deletion_service.py            # new
    ├── serializers/serializers.py                 # profile fields; password field factory;
    │                                              #   PasswordChange/AccountDeletion serializers
    ├── serializers/web_serializers.py             # web page serializers
    ├── views/account.py                           # PasswordChangeAPIView, AccountDeletionAPIView
    ├── views/account_deletion_page.py             # web page + its throttle
    ├── templates/accounts/account_deletion.html   # form, Google button, outcomes
    ├── urls.py                                    # + api/me/password/, api/me/delete/, conta/excluir/
    └── tests/fakes.py, unit/…, integration/…

docs/features/accounts.md
specs/accounts/spec.md, specs/constitution.md
```

**Structure Decision**: extend `features/accounts`; no new app. Two services rather than one
`AccountService` so each stays small and single-purpose.

## Implementation Order

1. Exceptions + DTOs (core); `RefreshTokenRepository`, `UserRepository.set_password/delete`;
   unit tests.
2. `LoginService.authenticate_credentials` / `verify_password` (login reuses the first);
   `GoogleAuthService.resolve_existing_account`; tests incl. lockout.
3. `PasswordChangeService`, `AccountDeletionService` on fakes.
4. Profile serializer fields + name validation; tests (incl. photo file removal).
5. API views, serializers, urls, DI; integration tests per contract table.
6. Web page: view, throttle, template, lockout marker; integration tests with CSRF enforced.
7. Docs/specs: `specs/accounts/spec.md`, constitution, `docs/features/accounts.md`.
8. Full suite, mypy, `makemigrations --check`.

Commits: spec/plan/tasks first (docs only); then code + tests + domain spec/constitution together
(the mypy hook checks the whole tree, so each commit must be consistent).

## Complexity Tracking

| Violation | Why needed | Simpler alternative rejected because |
|-----------|------------|--------------------------------------|
| Services take an HTTP request: a second and third `LoginService` method join `login()` (constitution Architecture) | Password change, deletion and the web page check a password, and the constitution requires every such check under django-axes, which needs the request (agreed with the app session) | `check_password()` without axes breaks the lockout rule; a per-request verifier port still needs the real request (R-01) |
| A server-rendered web page (constitution Deployment: "no web frontend") | Google Play requires account deletion from a web link, outside the app | Linking to an e-mail or a form outside the system means manual deletion by a person, slower and unverifiable; a JSON endpoint is not usable from a browser link |
