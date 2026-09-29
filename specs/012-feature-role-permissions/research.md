# Research: Feature-Scoped Permissions with Roles

Decisions for `specs/012-feature-role-permissions/spec.md`. The requester fixed the frame
(native `Group`/`Permission`, custom per-scope permissions, one generic permission class,
`is_admin` removed by data migration); these entries settle what that frame leaves open.

## R-01 — Where the scope permissions are declared

**Decision**: a table-less model `core.PanelScope` (`managed = False`, `default_permissions = ()`)
whose `Meta.permissions` lists every (scope, level) pair, generated from the `Scope` and `Level`
enumerations.

**Rationale**: a `Permission` row needs a `ContentType`, so it must hang off a model. The scopes
cross features, so no feature model is the owner; `core` may hold models shared by two or more
features (constitution, Architecture), and every feature with a management endpoint uses these.
An unmanaged model creates no table, and `default_permissions = ()` suppresses the automatic
`add_/change_/delete_/view_` rows the requester ruled out. Generating the list from the enums means
adding a scope is one enum line plus `makemigrations` (an `AlterModelOptions`).

**Alternatives considered**:
- *Proxy of `auth.Group`* — also gets its own content type, but ties "what a scope is" to "who
  holds it" and invites registering a second Group admin.
- *Permissions on `accounts.Profile`* — `accounts` is a feature; every other feature would depend
  on it for authorization.
- *Automatic per-model permissions* — rejected by the requester: one feature has several models.

## R-02 — Permission codenames

**Decision**: `<scope with "." as "_">__<level>`, e.g. `members__manage`,
`reports_hymnal_history__view`. Translation to `(Scope, Level)` goes through a dictionary built
from the enumerations; codenames are never parsed.

**Rationale**: a dot in a codename collides with Django's `"app_label.codename"` notation. The
double underscore keeps the scope readable in the Django admin permission list. A lookup table
means an unknown codename is simply ignored instead of mis-parsed.

**Alternatives considered**: one permission per scope with the level stored elsewhere — not
expressible with `Group.permissions` alone.

## R-03 — Reading a user's levels: repository query, not `user.has_perm`

**Decision**: a repository reads the user's role groups and, separately, the `core.PanelScope`
permissions attached to them (two queries). A pure function turns them into levels; Admin
membership short-circuits to `owner` on every scope.

**Rationale**:
- `User.has_perm` returns `True` for any active superuser before asking a backend. Spec FR-030
  says the superuser flag grants nothing, so the check cannot go through it.
- `has_perm` also merges `user_permissions` (direct grants) and every group, not only the three
  roles; the spec says levels come from roles alone (R-10).
- The architecture rule puts the ORM in repositories. The permission class calls a service, the
  service calls the repository.

Two queries per management request: one for group names (needed even when there are no
permissions — Admin holds none), one for the permissions. A single `values_list` with a LEFT
JOIN would work, but filtering the permission side by content type turns it into an inner join
and drops Admin; clarity wins over one query.

**Alternatives considered**: `ModelBackend` subclass that skips superusers — changes behaviour
for the Django admin too, where superuser must keep working.

## R-04 — Declaring scope and level on a view

**Decision**: a factory in `core/http/permissions.py`:

```python
scope_permission(Scope.MEMBERS) -> type[BasePermission]
scope_permission(Scope.REPORTS_HYMNAL_HISTORY, overrides={"PATCH": Level.OWNER, "POST": Level.OWNER})
```

It returns a `BasePermission` subclass, used as `permission_classes = [IsAuthenticated,
scope_permission(...)]` or instantiated inside `get_permissions()`.

**Rationale**: DRF instantiates each entry of `permission_classes` with no arguments, so
`HasFeaturePermission("members")` (an instance) does not fit; `functools.partial` does, but fails
the `permission_classes` type in the DRF stubs under mypy. A class factory is typed
(`type[BasePermission]`) and reads the same as the requester's sketch.

**Alternatives considered**: view attributes (`access_scope = Scope.MEMBERS`) read by one fixed
class — splits the rule across two places and makes the per-method `get_permissions` views
awkward.

## R-05 — Required level from the method; overrides

**Decision**: pure `required_level(method, overrides)` in `core/domain/access.py`:
`GET`/`HEAD`/`OPTIONS` → `view`; `POST`/`PUT`/`PATCH` → `manage`; `DELETE` → `owner`; any other
method → `owner` (fail closed). `scope_permission` validates overrides **when the class is
built**, i.e. at import: an override below its method's default raises `ValueError` naming the
method, the override and the default.

**Rationale**: spec FR-005 — a lower level must never take effect. Failing at import makes the
mistake impossible to deploy instead of silently ignored.

## R-06 — Role identity: group names are the enum slugs

**Decision**: `Role` is a `StrEnum` (`admin`, `leader`, `media`); the group's `name` is the slug.
Display names (Admin, Liderança, Mídia) live in a code mapping. Code always uses `Role.MEDIA`,
never `"media"` (spec, Roles).

**Rationale**: the slug is a stable key; renaming a display name must not revoke access. Groups
with other names are ignored (R-10).

## R-07 — Creating the roles: data migration that creates its own permission rows

**Decision**: `core/migrations/0005_seed_panel_roles.py` (data migration, reason at the top):
get-or-create the `ContentType` for `core.panelscope`, get-or-create every `Permission` row,
get-or-create the three groups, attach the Leader and Media levels. The matrix is **frozen as a
literal in the migration**, not imported from application code. Reverse is a no-op.

**Rationale**: Django creates the `Meta.permissions` rows in a `post_migrate` signal, after all
migrations. On a fresh database (tests, a new environment) they do not exist while the data
migration runs, and depending on `0004` does not change that; a migration that only looks them up
would leave the groups empty with no error (spec FR-025). Get-or-create is safe against the
later `post_migrate` pass, which also get-or-creates. Freezing the matrix keeps the migration's
meaning fixed if the code changes later. The no-op reverse is harmless: the rows it leaves are
recreated identically by a forward run.

## R-08 — Converting `is_admin`: irreversible, then drop the column

**Decision**: `accounts/migrations/0003_is_admin_to_admin_role.py` (data, reason at the top,
depends on `core.0005`) adds every `is_admin=True` user to the Admin group in one bulk insert
into the membership table; `0004` (generated) removes the field. The conversion is irreversible
(`RunPython` without reverse) — the requester dropped the rollback (spec clarification). Tested
with the same fake-unapply technique as `test_birth_date_split_migration.py` (011).

**Rationale**: an irreversible step says so; a no-op reverse would let a rollback re-add
`is_admin` as `False` for everyone without complaint. Recovery is the pre-deploy dump.

## R-09 — Layer placement

**Decision**:
- `core/domain/access.py` — `Role`, `Scope`, `Level`, display names, codename table,
  `required_level`, `resolve_grants`. Pure.
- `core/models/panel_scope.py` — the table-less model (R-01).
- `core/repositories/access_repository.py` — `RoleGrantRepository` Protocol + Django
  implementation.
- `core/application/access_service.py` + `core/application/dtos/access_dtos.py` —
  `AccessService.grants_for(user_id) -> AccessGrantsDTO`.
- `core/http/permissions.py` — `scope_permission` factory; `IsAdminUser` removed.

The permission class gets `AccessService` through `@inject` + `Provide[Container.access_service]`,
like views do; `core.http.permissions` joins the wiring list.

**Rationale**: every feature reads it; features cannot import each other. Services still know
nothing of HTTP: the service answers "which levels does this user hold", the permission class
turns the method into a required level.

## R-10 — What counts toward levels

**Decision**: only the three role groups, and only `core.PanelScope` permissions attached to
them. Ignored: other groups, direct `user_permissions`, `is_superuser`, `is_staff`.

**Rationale**: spec — levels come from roles alone (FR-030), Django admin access is independent
(FR-027). An extra group created in the Django admin grants nothing in the panel, which matches
"three roles".

## R-11 — Profile response

**Decision**: `GET`/`PATCH api/me/profile/` add `roles` (`[{"id", "name"}]`, ordered Admin,
Leader, Media) and `permissions` (every scope as a key, value `"view" | "manage" | "owner" |
null`); `is_admin` removed. The view asks `AccessService` and passes the grants to the serializer
through its context. Contract in `contracts/profile-api.md`.

**Rationale**: every scope present lets the app switch on keys without guessing which are
missing; `null` is "no access". Reserved scopes (`events`, `notices`) are included (spec,
Assumptions). The body already drives the ETag, so a role change changes it.

## R-12 — Media

**Decision**: `MediaViewer.is_leader` → `can_view_members`; `MediaAudience.LEADER` →
`MediaAudience.MEMBERS_SCOPE`. The view fills it with
`scope_permission(Scope.MEMBERS)().has_permission(request, self)` — the endpoint only allows
`GET`/`HEAD`, so the required level is `view`.

**Rationale**: spec FR-017. The view keeps building the viewer from the same permission classes
every endpoint uses (its existing comment), so "can see members" is decided one way.

## R-13 — Test helpers

**Decision**: `conftest.make_role_client(*roles)` adds the user to the seeded groups;
`make_admin_client` becomes a thin wrapper over it. A single parametrised integration test walks
the spec's Endpoint Classification × {Admin, Leader, Media, none, superuser without role} and
asserts `403` exactly where the matrix says so (any other status means the permission passed).

**Rationale**: SC-004 asks for every combination covered; one table-driven test mirrors the
spec's table so a drift shows as one failing row.

## R-14 — Specs to update before code

`specs/constitution.md`, `specs/members/spec.md`, `specs/accounts/spec.md`,
`specs/songs/spec.md`, `specs/schedule/spec.md`, `specs/gallery/spec.md` (MEDIA will manage the
gallery), and the feature specs `specs/006-hymnal-view-history/spec.md`,
`specs/009-protected-media-access/spec.md`, `specs/010-members-management/spec.md` (spec FR-029).
The constitution gets one Authorization rule (scope + level on every management endpoint,
roles only) and its "leader" wording under Sensitive data and Media becomes "`view` on
`members`".
