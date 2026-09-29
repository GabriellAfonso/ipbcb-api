# Implementation Plan: Feature-Scoped Permissions with Roles

**Branch**: `012-feature-role-permissions` | **Date**: 2026-09-28 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/012-feature-role-permissions/spec.md`

## Summary

Replace `Profile.is_admin` / `IsAdminUser` with per-scope levels (`view` < `manage` < `owner`)
bundled into three roles (Admin, Liderança, Mídia) stored as Django `Group`s. Scope permissions
are custom `Permission` rows declared on a table-less `core.PanelScope` model. One permission
factory, `scope_permission(scope, overrides=…)`, derives the required level from the HTTP method
and asks `AccessService` for the caller's levels; the service reads role groups through a
repository and never goes through `user.has_perm` (which lets superusers through). Admin is
`owner` of every scope in code. A data migration seeds the groups **with** their permissions,
creating the permission rows itself because `post_migrate` runs too late; a second one converts
`is_admin=True` into Admin membership, then the column is dropped. `api/me/profile/` returns
`roles` and `permissions` instead of `is_admin`. Media's `members/` rule becomes "`view` on
`members`".

## Technical Context

**Language/Version**: Python 3.14, `.venv_windows`

**Primary Dependencies**: Django 6 (`django.contrib.auth` groups/permissions, `contenttypes`),
DRF, dependency-injector, Pydantic. No new dependency.

**Storage**: PostgreSQL in production, SQLite in tests. Four migrations (data-model.md).

**Testing**: pytest + pytest-django; named fake `FakeRoleGrantRepository` for service unit tests;
migration tests through `MigrationExecutor` with the fake-unapply technique from 011; mypy, ruff,
bandit.

**Target Platform**: Linux container behind nginx, prefix `/ipbcb/`.

**Project Type**: Web service (REST API), single Android client.

**Performance Goals**: Two small queries per management request (role names, scope permissions).
No caching: a role removed in the Django admin applies on the next request.

**Constraints**: Services never see HTTP, methods or permission classes. Superuser, `is_staff`,
direct user permissions and non-role groups grant nothing. Breaking `is_admin` removal accepted.

**Scale/Scope**: A handful of role holders; 7 scopes; 24 classified endpoint-methods across
members, schedule, songs and hymnal history; ~20 test files touched (helper swap).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design — result unchanged.*

| Rule (`specs/constitution.md`, `CLAUDE.md`) | Status |
|---|---|
| `IsAuthenticated` on every authenticated view | ✅ kept explicitly next to `scope_permission(...)` everywhere |
| Features never import each other; `core` models only if shared by 2+ features | ✅ `PanelScope` and the access service live in `core`, used by members, schedule, songs, media, accounts (R-09) |
| Views → services → repositories; ORM only in repositories | ✅ permission class → `AccessService` → `RoleGrantRepository` (R-03, R-09) |
| Services never import HTTP objects | ✅ method → level mapping stays in `core/http` + pure domain (R-05) |
| DI through `config/di.py`; injection, not globals | ✅ `access_service` provider; `core.http.permissions` and profile view wired (R-09) |
| DTOs are Pydantic | ✅ `AccessGrantsDTO`, `RoleGrantRowsDTO` |
| Domain errors, messages with value and expected shape | ✅ override `ValueError` names method, override, default (R-05) |
| Sensitive data: members | ✅ Media role gets no `members` level, no `members/` files; constitution wording updated (R-14) |
| Caching: user-dependent bodies private | ✅ profile already `private=True`; its body now also varies by role, covered by the ETag |
| Migrations generated, data migrations with reason at top | ✅ `core/0004` and `accounts/0004` generated; `core/0005` and `accounts/0003` data with reason (R-07, R-08) |
| Verification against a restored production dump | ✅ quickstart §3 |
| Models have `__str__`, `Meta.ordering`, `Meta.verbose_name` | ✅ `PanelScope` has all three, although it never has rows |
| Spec before code | ✅ domain specs and constitution updated first (Implementation Order step 0) |

Gate: **pass**.

## Technical Decisions

Full reasoning in [research.md](research.md).

- **D-1** Django `Group` = role, custom `Permission` = (scope, level), declared in
  `Meta.permissions` of the table-less `core.PanelScope`; no automatic per-model permissions
  (requester decision; R-01).
- **D-2** Codename `<scope with . as _>__<level>`, mapped through a table built from the enums
  (R-02).
- **D-3** Levels read by a repository query restricted to the three role groups and
  `PanelScope` permissions; `user.has_perm` not used, so superuser grants nothing (spec FR-030;
  R-03, R-10).
- **D-4** `scope_permission(scope, overrides=None) -> type[BasePermission]` in
  `core/http/permissions.py`; `IsAdminUser` removed (requester decision; R-04).
- **D-5** Required level by method with fail-closed default; overrides below the default raise at
  import (R-05).
- **D-6** Admin = `owner` of every `Scope` in `resolve_grants`, never read from the database
  (requester decision; spec FR-008).
- **D-7** Group names are the `Role` slugs; display names in code (R-06).
- **D-8** `core/0005` seeds groups and matrix, creating permission rows itself; frozen matrix;
  reverse no-op (R-07).
- **D-9** `accounts/0003` converts `is_admin`, irreversible; `accounts/0004` drops the column
  (requester decision; R-08).
- **D-10** Profile gains `roles` + `permissions` (all scopes, `null` for none), loses `is_admin`
  (R-11, contracts/profile-api.md).
- **D-11** Media: `MediaAudience.MEMBERS_SCOPE`, `MediaViewer.can_view_members`, filled by
  `scope_permission(Scope.MEMBERS)` (R-12).
- **D-12** Roles assigned only through the existing Django admin user form (`groups`); no
  endpoint; `is_staff` untouched (requester decision).

## Implementation Order

Each step leaves the tree type-correct for the whole-tree mypy hook.

0. **Specs** (docs commit): update `specs/constitution.md` and the domain/feature specs listed in
   research R-14 to roles and scopes.
1. **Domain**: `core/domain/access.py` (`Role`, `Scope`, `Level`, display names, codename table,
   `required_level`, `validate_overrides`, `resolve_grants`). Unit tests.
2. **Model + seed**: `core/models/panel_scope.py`, `makemigrations core` → `0004`; hand-write
   `0005_seed_panel_roles.py` with the reason at the top. Test: fresh database holds the three
   groups with exactly the matrix; migrating twice creates no duplicates.
3. **Repository + service + DI**: `RoleGrantRepository` Protocol and Django implementation,
   `AccessGrantsDTO`, `AccessService.grants_for`; `access_service` provider; unit tests with
   `FakeRoleGrantRepository`, integration test of the repository (superuser, extra group, direct
   user permission all ignored).
4. **Permission factory**: `scope_permission` next to `IsAdminUser` (both exist for now); wire
   `core.http.permissions`. Unit tests: required level per method, override, anonymous user.
   `conftest.make_role_client(*roles)`.
5. **Switch endpoints**, one commit per feature, tests switched with them:
   members (`admin_members`, `admin_member_photo`, `admin_member_history`), schedule, songs
   (`songs`, `register_plays`), hymnal history (with the `owner` overrides), media
   (`MediaAudience`, `MediaViewer`, view). Access-matrix integration test grows with each.
6. **Profile**: `ProfileSerializer` gains `roles`/`permissions` from context; view injects
   `AccessService`. Tests per contracts/profile-api.md.
7. **Remove the flag**: drop `is_admin` from the model, `makemigrations accounts` → `0004`; drop
   it from the serializer, `IsAdminUser` and its tests, `make_admin_client`'s flag. Quickstart §2
   grep clean. The conversion `accounts/0003` (data, irreversible, with its migration test) lands
   earlier, right after step 4: it only adds group memberships, so it is safe while `is_admin`
   still exists, and `make_admin_client` sets both during the transition.
8. **Validation**: quickstart §1, §3 against the production dump, §4.

## Project Structure

### Documentation (this feature)

```text
specs/012-feature-role-permissions/
├── spec.md
├── plan.md                          # this file
├── research.md                      # R-01 … R-14
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── profile-api.md
│   └── management-access.md
├── checklists/requirements.md
└── tasks.md                         # /speckit-tasks
```

### Source Code

```text
server/
├── conftest.py                                   # make_role_client; make_admin_client wraps it
├── config/di.py                                  # access_service; wire core.http.permissions
├── core/
│   ├── domain/access.py                          # Role, Scope, Level, required_level, resolve_grants
│   ├── models/panel_scope.py                     # table-less, Meta.permissions
│   ├── migrations/
│   │   ├── 0004_panelscope.py                    # generated
│   │   └── 0005_seed_panel_roles.py              # data: groups + matrix
│   ├── repositories/
│   │   ├── interfaces.py                         # RoleGrantRepository Protocol
│   │   └── access_repository.py                  # Django implementation
│   ├── application/
│   │   ├── access_service.py
│   │   └── dtos/access_dtos.py
│   ├── http/permissions.py                       # scope_permission; IsAdminUser removed
│   └── tests/
│       ├── fakes.py                              # FakeRoleGrantRepository
│       ├── unit/test_access.py
│       ├── unit/test_access_service.py
│       ├── unit/test_scope_permission.py
│       ├── integration/test_panel_roles_seed.py
│       ├── integration/test_access_repository.py
│       └── integration/test_management_access_matrix.py
└── features/
    ├── accounts/
    │   ├── models/profile.py                     # is_admin removed
    │   ├── migrations/0003_is_admin_to_admin_role.py, 0004_remove_profile_is_admin.py
    │   ├── serializers/serializers.py            # roles, permissions; no is_admin
    │   ├── views/profile.py                      # injects AccessService
    │   └── tests/…                               # profile API, conversion migration, permissions
    ├── members/views/admin_members.py, admin_member_photo.py, admin_member_history.py
    ├── schedule/views/schedule.py
    ├── songs/views/songs.py, register_plays.py, hymnal_history.py
    └── media/domain/media_rules.py, dtos/media_dtos.py, services/media_access_service.py,
        views/media_file.py
```

**Structure Decision**: the access model is cross-feature, so it lives in `core` split by layer
like a feature (domain, models, repositories, application, http). `core/repositories/` is new;
it follows the feature layout (`interfaces.py` + implementation).

## Out of scope, found during planning (reported, not changed)

- `AdminMemberDetailAPIView` etc. keep the `Admin` prefix in class names and `/api/admin/` in
  URLs; with roles the prefix now means "management panel", not "Admin role". Renaming would
  break the app for no behavioural gain.
- Django admin: a non-superuser staff account can still edit groups only if given
  `auth.change_group` by hand — unchanged, roles are maintained by whoever already runs accounts.

## Complexity Tracking

No constitution violations to justify.
