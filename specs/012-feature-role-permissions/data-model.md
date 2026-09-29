# Data Model: Feature-Scoped Permissions with Roles

## Domain values (`core/domain/access.py`, pure)

### `Role` (StrEnum)

| Member        | Value (group name) | Display name |
|---------------|--------------------|--------------|
| `Role.ADMIN`  | `admin`            | Admin        |
| `Role.LEADER` | `leader`           | Liderança    |
| `Role.MEDIA`  | `media`            | Mídia        |

Order of declaration is the order the profile lists roles in.

### `Scope` (StrEnum)

`members`, `schedule`, `songs`, `gallery`, `events`, `notices`, `reports.hymnal_history`.
The value is the wire name (profile keys). Adding a report means adding `reports.<name>` here.

### `Level` (IntEnum)

| Member         | Rank | Wire name |
|----------------|------|-----------|
| `Level.VIEW`   | 1    | `view`    |
| `Level.MANAGE` | 2    | `manage`  |
| `Level.OWNER`  | 3    | `owner`   |

`a >= b` means "`a` includes `b`".

### Codename table

`PERMISSION_BY_CODENAME: Mapping[str, tuple[Scope, Level]]`, built from the two enums:
`codename(scope, level) = scope.value.replace(".", "_") + "__" + level.name.lower()`.
21 entries (7 scopes × 3 levels).

### Functions

| Function | Contract |
|----------|----------|
| `required_level(method, overrides) -> Level` | Default by method (research R-05); override replaces it; unknown method → `OWNER` |
| `validate_overrides(overrides) -> None` | `ValueError` if any override is below its method's default, message names method, override and default |
| `resolve_grants(roles, codenames) -> dict[Scope, Level]` | `ADMIN` in roles → `OWNER` for every `Scope`. Otherwise the highest level per scope among known codenames; unknown codenames ignored; scopes without a grant absent |

## Persistence

### `core.PanelScope` (new, table-less)

| Meta option           | Value                                              |
|-----------------------|----------------------------------------------------|
| `managed`             | `False` — no table                                 |
| `default_permissions` | `()` — no automatic add/change/delete/view         |
| `permissions`         | one `(codename, name)` per `Scope × Level`; name like `"members: manage"` |
| `verbose_name`        | `"Panel scope"`                                    |
| `ordering`            | `[]` (no rows ever exist; set for the constitution rule) |

`__str__` returns a fixed label. It exists only as the `ContentType` the permissions hang on.

### `auth.Group` (existing, Django)

Three rows, `name` ∈ `Role` values. `permissions` holds `core.PanelScope` rows only for Leader and
Media. Admin holds none: its levels are implied in code.

**Initial content** (seeded by `core/migrations/0005_seed_panel_roles.py`, frozen literal):

| Group    | Permissions                                                                 |
|----------|-----------------------------------------------------------------------------|
| `admin`  | —                                                                           |
| `leader` | `members__manage`, `schedule__manage`, `songs__manage`, `gallery__manage`, `events__manage`, `notices__manage`, `reports_hymnal_history__view` |
| `media`  | `gallery__manage`, `events__manage`, `notices__manage`, `reports_hymnal_history__view` |

Only the single highest level is stored per scope; lower levels follow from the ordering.

`core/migrations/0006_gallery_owner_for_leader_media.py` (feature 013) swaps `gallery__manage`
for `gallery__owner` in `leader` and `media`.

### `accounts.User` (existing)

Unchanged. Roles are `user.groups`; the Django admin's user form already edits them.

### `accounts.Profile` (changed)

| Field       | Change  |
|-------------|---------|
| `is_admin`  | removed (`0004`, generated) after conversion (`0003`, data) |
| `is_member` | unchanged |

## Migrations

| Migration | Kind | Content |
|-----------|------|---------|
| `core/0004_panelscope` | generated | `CreateModel` unmanaged with the 21 permissions |
| `core/0005_seed_panel_roles` | data | get-or-create content type, 21 permissions, 3 groups; attach matrix. Reverse no-op. Depends on `core.0004`, `auth` latest, `contenttypes` latest |
| `accounts/0003_is_admin_to_admin_role` | data | `is_admin=True` → member of group `admin`. Irreversible. Depends on `accounts.0002`, `core.0005` |
| `accounts/0004_remove_profile_is_admin` | generated | `RemoveField` |

## DTOs (`core/application/dtos/access_dtos.py`)

### `AccessGrantsDTO` (`StrictBaseModel`, frozen)

| Field    | Type                   | Notes                                   |
|----------|------------------------|-----------------------------------------|
| `roles`  | `list[Role]`           | in `Role` declaration order             |
| `levels` | `dict[Scope, Level]`   | only reachable scopes                   |

Method `allows(scope, level) -> bool`: `levels.get(scope)` is not `None` and `>= level`.

### `RoleGrantRowsDTO` (repository output)

| Field       | Type        | Notes                                             |
|-------------|-------------|---------------------------------------------------|
| `role_names`| `list[str]` | user's group names that are `Role` values         |
| `codenames` | `list[str]` | `core.PanelScope` codenames attached to those groups |

## Media (`features/media`)

| Before                     | After                          |
|----------------------------|--------------------------------|
| `MediaAudience.LEADER`     | `MediaAudience.MEMBERS_SCOPE`  |
| `MediaViewer.is_leader`    | `MediaViewer.can_view_members` |
