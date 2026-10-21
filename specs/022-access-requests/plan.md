# Implementation Plan: Member Access and Access Requests

**Branch**: `022-access-requests` | **Date**: 2026-10-21 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/022-access-requests/spec.md`

## Summary

`Profile.is_member` becomes `Profile.member_access` through a hand-written `RenameField` (R-01),
and the permission `IsMemberUser` becomes `HasMemberAccess` = flag **or** an Admin/Liderança role,
decided by a pure rule in `core.domain.access` (R-02). The accounts feature gains the
`AccessRequest` model, a self-service endpoint to create requests, and the "Perfis" management
endpoints under a new scope `profiles` (R-03, seeded by a data migration). Push goes through the
existing `PushService` with three new message types; `PushMessage` gains optional fields (R-05).
`/me` gets `member_access`, `access_status`, `access_requests_blocked` and
`data_correction_pending` and keeps `is_member`. The account's own roll data is served by a new
`GET api/me/member/` in the members feature, `private, no-store` and without ETag, never in `/me`
(R-06).

## Technical Context

**Language/Version**: Python 3.14, Django 6.0.8

**Primary Dependencies**: DRF, SimpleJWT, Pydantic 2, `dependency-injector`, the FCM sender of
spec 017. No new dependency

**Storage**: PostgreSQL (prod), SQLite (tests)

**Testing**: pytest + pytest-django from `server/`; unit tests on named fakes
(`features/accounts/tests/fakes.py`), integration tests through `APIClient`

**Target Platform**: Linux container behind nginx at `/ipbcb/`

**Project Type**: web service (REST API for the Android app)

**Performance Goals**: request creation ≤ 5 queries; the "Perfis" list one query for accounts plus
one for pending requests (no query per row)

**Constraints**: functions 4–20 lines, files < 500 lines, no cross-feature imports, canonical
error shape, pt-BR user-facing text, roll data never logged or cached

**Scale/Scope**: hundreds of accounts; requests in the tens per month

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Rule | How this plan complies |
|------|------------------------|
| One scope per management endpoint via `scope_permission`; levels from roles alone | Every "Perfis" endpoint declares `Scope.PROFILES`; GET `view`, POST/PATCH `manage`; no `lowered=`. Liderança gets `profiles__manage` by data migration, Mídia nothing, Admin `owner` in code |
| "Church membership (`is_member`) is a separate axis and never grants a level" | Kept in substance — member access still grants no level. **Amendment**: the wording becomes `member_access`, and records that Admin and Liderança roles *imply* member access (Complexity Tracking) |
| `IsAuthenticated` on protected views | Every new view lists it |
| Input through DRF serializers; `require_object_body` | New serializers for request creation, deny, PATCH; `require_object_body` before them |
| No queries in loops | List: accounts with `select_related("profile__member")` + an `Exists` annotation for roles; pending requests in one query grouped in Python |
| Repositories only touch the ORM; features never import each other | `accounts` reaches `members.Member` only through `apps.get_model` and lookups by string, like `core/repositories/worship_repository.py`; `members` reads its own `Member` by `profile__user_id` |
| Sensitive data: members | `api/me/member/` lists fields explicitly, answers `private, no-store` with no ETag, logs only `member_id` (never fields) |
| Caching: caller-specific responses private | `/me` keeps `private`; "Perfis" GETs use `_not_modified_or_response(private=True)`; `api/me/member/` sets `private, no-store` + `Vary: Authorization` itself |
| Migrations: `RenameField` hand-written with compensating controls | `accounts/0006` hand-written, reason at the top, verification against a production dump and rollback listed in quickstart (R-01) |
| Error shape | New domain exceptions with their own `error_code`; 429 added to the domain status map (R-04) |
| DI container, Pydantic DTOs | Providers in `config/di.py`; DTOs in `features/accounts/dtos.py` |
| Specs and code together | 022 spec/plan/tasks, `specs/accounts/spec.md`, `specs/012…/spec.md`, `specs/members/spec.md`, constitution |

**Gate**: PASS with one justified amendment. Re-checked after Phase 1: PASS.

## Project Structure

### Documentation (this feature)

```text
specs/022-access-requests/
├── spec.md
├── plan.md              # this file
├── research.md          # R-01 … R-09
├── data-model.md
├── quickstart.md
├── contracts/
│   └── access-api.md    # the contract the app builds against
├── checklists/
│   └── requirements.md
└── tasks.md
```

### Source Code

```text
server/
├── config/di.py                                   # + access_request_repository,
│                                                  #   managed_account_repository, services, wiring
├── core/
│   ├── domain/access.py                           # + Scope.PROFILES, MEMBER_ACCESS_ROLES,
│   │                                              #   has_member_access()
│   ├── domain/base_exceptions.py                  # + RateLimitedError
│   ├── domain/access_request_exceptions.py        # new; re-exported by exceptions.py
│   ├── domain/push.py                             # + three message types
│   ├── application/dtos/push_dtos.py              # PushMessage optional fields
│   ├── application/push_service.py                # log without a date
│   ├── http/exceptions.py                         # RateLimitedError → 429
│   ├── http/permissions.py                        # IsMemberUser → HasMemberAccess
│   └── migrations/0009_…, 0010_profiles_scope_for_leader.py
├── features/accounts/
│   ├── models/profile.py, models/access_request.py
│   ├── migrations/0006_rename_is_member_member_access.py (hand-written), 0007_… (generated)
│   ├── domain/access_requests.py                  # enums, limits, pure rules
│   ├── dtos.py                                    # access-request and managed-account DTOs
│   ├── repositories/access_request_repository.py, managed_account_repository.py
│   ├── services/access_request_service.py         # create + the /me access state
│   ├── services/profile_management_service.py    # "Perfis"
│   ├── serializers/access_request_serializers.py
│   ├── views/access_requests.py, views/admin_profiles.py, views/profile.py
│   ├── admin.py, urls.py
│   └── tests/…
├── features/members/
│   ├── repositories/member_repository.py          # + get_own_record
│   ├── services/member_service.py                 # + get_own_record
│   ├── serializers/own_member_serializer.py, views/own_member.py, urls.py
│   └── tests/…
└── features/{events,gallery,media,members,schedule}/…  # IsMemberUser → HasMemberAccess
```

**Structure Decision**: requests and "Perfis" live in `features/accounts`, which owns `Profile`.
The roll read lives in `features/members`, which owns `Member`. No new app.

## Implementation Order

1. Rename: hand-written migration, model, permission (`HasMemberAccess` with the role rule), every
   caller, `/me` compat fields, conftest helpers; full suite green.
2. Scope `profiles`: enum, generated `AlterModelOptions`, data migration for Liderança.
3. Model `AccessRequest` + `access_requests_blocked` (generated migration), domain rules,
   exceptions, DTOs, repositories with tests.
4. `AccessRequestService` (create, access state) on fakes; push types; `POST api/me/access-requests/`;
   `/me` fields.
5. `ProfileManagementService` and the "Perfis" endpoints; push on decisions.
6. `GET api/me/member/`.
7. Specs (domain specs, spec 012 matrix, constitution), Django admin, full suite, mypy,
   `makemigrations --check`.

## Complexity Tracking

| Violation | Why needed | Simpler alternative rejected because |
|-----------|------------|--------------------------------------|
| Hand-written `RenameField` (constitution, Migrations) | Renaming the flag must keep every value; generated non-interactively it becomes remove + add and wipes everyone's access | Keeping the column name `is_member` behind a model field `member_access` (`db_column`) leaves the confusing name in the schema and the admin forever |
| Constitution sentence "membership is a separate axis and never grants a level" amended | Leaders without the flag get 403 on member screens ("Gerar Escala"); the app computes `canOpenPanel` from roles, so a member *role* would open the panel to every member | Granting the flag to every leader by hand drifts as roles change; a `Role.MEMBER` breaks `canOpenPanel` |
