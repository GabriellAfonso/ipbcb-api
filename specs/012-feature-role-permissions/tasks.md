---

description: "Task list for Feature-Scoped Permissions with Roles"
---

# Tasks: Feature-Scoped Permissions with Roles

**Input**: Design documents from `specs/012-feature-role-permissions/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/profile-api.md,
contracts/management-access.md, quickstart.md

**Tests**: Included. CLAUDE.md §10 requires a test for every new function, and the request lists
the expected tests (per role × scope × method, Leader 403 on every DELETE, the override, Admin
without stored permissions, union, Media on members, migration, profile). Fakes are named classes
in `server/core/tests/fakes.py`.

**Organization**: Tasks are grouped by user story. Paths are relative to the repository root.
Run commands from `server/` with `.venv_windows` active (PowerShell).

**Commit rule**: the mypy pre-commit hook checks the whole tree, so every commit must leave it
type-correct. `IsAdminUser` and `Profile.is_admin` stay until Phase 8; during the transition
`make_admin_client` sets **both** the flag and the Admin group (T016), so each endpoint can switch
in its own commit with its tests still green.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1–US5 from spec.md

---

## Phase 1: Setup

**Purpose**: Known-green baseline, and specs updated before any code (CLAUDE.md §6.2).

- [X] T001 Run `pytest` and `mypy .` from `server/` on branch `012-feature-role-permissions` and confirm both pass before any change
- [X] T002 Update the specs to roles and scopes (research R-14, spec FR-029), one docs commit: in `specs/constitution.md` add under Authentication & Authorization a rule "every management endpoint declares one scope; the required level comes from the method (GET view, POST/PUT/PATCH manage, DELETE owner) or a higher per-endpoint override; levels come from roles only — superuser, `is_staff` and direct user permissions grant nothing" pointing to `specs/012-feature-role-permissions/`, and replace "leader-only responses" / "readable only by leaders" / "leaders included" under Sensitive data and Media with "`view` on `members`" wording; in `specs/members/spec.md` rewrite the Leader endpoints section header and auth line to "`IsAuthenticated` + `scope_permission(Scope.MEMBERS)`", add the level per row from spec 012's members table (DELETE rows → `owner`, Admin only), and replace "leader" with "role holder with `view` on `members`" where it means access; in `specs/accounts/spec.md` replace `is_admin` in the Profile model and in `GET/PATCH api/me/profile/` with `roles` and `permissions` per `specs/012-feature-role-permissions/contracts/profile-api.md`; in `specs/songs/spec.md` and `specs/schedule/spec.md` replace every `IsAdminUser` auth line with the scope and level from spec 012's classification (hymnal settings PATCH and service-window POST/PATCH `owner`; service-window GETs `view`); in `specs/gallery/spec.md` add a line that gallery writes stay in the Django admin and the future write endpoints belong to scope `gallery` (Admin owner, Leader and Media manage); in `specs/006-hymnal-view-history/spec.md`, `specs/009-protected-media-access/spec.md` and `specs/010-members-management/spec.md` add a note at the top "Access terms superseded by `specs/012-feature-role-permissions/`: 'admin'/'leader' below meant `Profile.is_admin`, now roles and scopes" and fix the rule tables that name `is_admin`/`IsAdminUser` (009 folder table: `members` → "`view` on `members`")

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Domain values, the permission rows, the seeded roles, the access service and the
permission factory. Everything is additive: `IsAdminUser` keeps working.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T003 Create `server/core/domain/access.py` (pure, no Django import): `Role(StrEnum)` `ADMIN="admin"`, `LEADER="leader"`, `MEDIA="media"`; `ROLE_DISPLAY_NAMES: Mapping[Role, str]` (`Admin`, `Liderança`, `Mídia`); `Scope(StrEnum)` `MEMBERS="members"`, `SCHEDULE="schedule"`, `SONGS="songs"`, `GALLERY="gallery"`, `EVENTS="events"`, `NOTICES="notices"`, `REPORTS_HYMNAL_HISTORY="reports.hymnal_history"`; `Level(IntEnum)` `VIEW=1`, `MANAGE=2`, `OWNER=3` with a `wire_name` property returning `name.lower()`; `codename(scope, level) -> str` = `scope.value.replace(".", "_") + "__" + level.name.lower()`; `PERMISSION_BY_CODENAME: Mapping[str, tuple[Scope, Level]]` built from both enums (`MappingProxyType`); `panel_scope_permissions() -> list[tuple[str, str]]` returning `(codename, f"{scope.value}: {level.wire_name}")` for every pair; `DEFAULT_LEVEL_BY_METHOD` (`GET`/`HEAD`/`OPTIONS` → VIEW, `POST`/`PUT`/`PATCH` → MANAGE, `DELETE` → OWNER); `required_level(method: str, overrides: Mapping[str, Level]) -> Level` (override if present, else default, unknown method → OWNER — fail closed); `validate_overrides(overrides: Mapping[str, Level]) -> None` raising `ValueError` like `"Override PATCH=VIEW is below the method default MANAGE; overrides may only raise the level."` (and for an unknown method: `"Override for unknown method 'FOO'; expected one of GET, HEAD, OPTIONS, POST, PUT, PATCH, DELETE."`); `resolve_grants(roles: Collection[Role], codenames: Iterable[str]) -> dict[Scope, Level]` (ADMIN → OWNER for every `Scope` without reading codenames; else max level per scope among codenames in `PERMISSION_BY_CODENAME`, unknown ignored, unreached scopes absent). Comment on the Admin branch: why it ignores stored permissions (spec FR-008 — a new scope can never lock Admin out). Each public function has a docstring with intent and one example; functions 4-20 lines
- [X] T004 [P] Create `server/core/tests/unit/test_access.py`: `required_level` for every method in `DEFAULT_LEVEL_BY_METHOD`, for `"TRACE"` (→ OWNER) and with an override (`{"PATCH": Level.OWNER}` → OWNER for PATCH, GET unchanged); `validate_overrides` accepts equal and higher, raises for `{"PATCH": Level.VIEW}` and `{"DELETE": Level.MANAGE}` with `match=` on the method and both levels, raises for `{"FOO": Level.OWNER}`; `codename` for `MEMBERS/MANAGE` (`"members__manage"`) and `REPORTS_HYMNAL_HISTORY/VIEW` (`"reports_hymnal_history__view"`); `PERMISSION_BY_CODENAME` has 21 entries and round-trips every pair; `resolve_grants`: `[ADMIN]` with no codenames → OWNER on all 7 scopes (spec: Admin without stored permissions), `[LEADER]` with the Leader codenames of `data-model.md` → the Leader column, `[]` with codenames → `{}`, two roles `[LEADER, MEDIA]` → highest per scope (`gallery` MANAGE), `members__view` + `members__owner` → OWNER, unknown codename `"view_member"` ignored; `ROLE_DISPLAY_NAMES` covers every `Role`
- [X] T005 Create `server/core/models/panel_scope.py` with `class PanelScope(models.Model)` and `Meta`: `managed = False`, `default_permissions = ()`, `permissions = panel_scope_permissions()`, `verbose_name = "Panel scope"`, `verbose_name_plural = "Panel scopes"`, `ordering: list[str] = []`; `__str__` returns `"Panel scope"`; module docstring: table-less, exists only as the content type the scope permissions hang on (research R-01), never query it. Export it in `server/core/models/__init__.py` like `ChurchService`
- [X] T006 Run `python manage.py makemigrations core` and keep the generated `server/core/migrations/0004_*.py` unedited (CreateModel, `managed: False`, 21 permissions). Rename the file only if Django names it oddly, to `0004_panelscope.py`
- [X] T007 Create hand-written `server/core/migrations/0005_seed_panel_roles.py`. Top docstring (CLAUDE.md §5): reason — the three roles must exist with their levels right after deploy, or Leader and Media would deny every request with no error (spec FR-025); why it creates the permission rows itself — Django creates `Meta.permissions` rows in `post_migrate`, after every migration, so on a fresh database they do not exist yet and depending on 0004 does not help (research R-07); why the matrix is a frozen literal here instead of an import; why the reverse is a no-op (forward is get-or-create, a re-run is identical). Dependencies: `("core", "0004_…")`, `("auth", "0012_alter_user_first_name_max_length")` (or the latest `auth` migration installed — check with `showmigrations auth`), `("contenttypes", "0002_remove_content_type_name")`. Body: module constants `SCOPE_CODENAMES` (the 21 `(codename, name)` pairs written out literally) and `ROLE_PERMISSIONS = {"admin": [], "leader": [...7...], "media": [...4...]}` exactly as `data-model.md` Initial content; `forward(apps, schema_editor)` gets `ContentType` via `get_or_create(app_label="core", model="panelscope")`, `Permission.objects.get_or_create(content_type=…, codename=…, defaults={"name": …})` for all 21, `Group.objects.get_or_create(name=…)` for each role and `group.permissions.add(*…)`; split into helpers of ≤20 lines; `operations = [migrations.RunPython(forward, migrations.RunPython.noop)]`
- [X] T008 [P] Create `server/core/tests/integration/test_panel_roles_seed.py` (`@pytest.mark.django_db`): the test database (migrated) has exactly the groups `admin`, `leader`, `media`; the codenames of `core.panelscope` permissions attached to each group equal the `data-model.md` table (Admin empty, Leader 7, Media 4) — write the expected table in the test module, not imported from app code; there are exactly 21 `core.panelscope` permissions and no duplicate codename (the `post_migrate` pass met the seeded rows — spec US1 scenario 5); running `call_command("migrate", verbosity=0)` again changes nothing
- [X] T009 Create `server/core/application/dtos/access_dtos.py`: `AccessGrantsDTO(StrictBaseModel)` frozen, fields `roles: list[Role]`, `levels: dict[Scope, Level]`, method `allows(scope: Scope, level: Level) -> bool` and `level_for(scope: Scope) -> Level | None`; `RoleGrantRowsDTO(StrictBaseModel)` with `role_names: list[str]`, `codenames: list[str]`. Export from `server/core/application/dtos/__init__.py` if that module re-exports the others
- [X] T010 Create `server/core/repositories/__init__.py`, `server/core/repositories/interfaces.py` with `class RoleGrantRepository(Protocol)`: `def role_grants(self, user_id: UUID) -> RoleGrantRowsDTO`, and `server/core/repositories/access_repository.py` with `RoleGrantRepositoryImpl` doing two queries (research R-03): group names `Group.objects.filter(user__pk=user_id, name__in=[r.value for r in Role]).values_list("name", flat=True)` and codenames `Permission.objects.filter(group__user__pk=user_id, group__name__in=…, content_type__app_label="core", content_type__model="panelscope").values_list("codename", flat=True).distinct()`. Comment: why not `user.has_perm` (superuser shortcut, direct permissions, other groups — spec FR-030, research R-10)
- [X] T011 Create `server/core/application/access_service.py` with `class AccessService` taking `role_grant_repository: RoleGrantRepository` in `__init__`, and `grants_for(user_id: UUID) -> AccessGrantsDTO`: reads rows, maps names to `Role` in `Role` declaration order, calls `resolve_grants`. Docstring with intent and example. Register in `server/config/di.py`: `role_grant_repository = providers.Factory(RoleGrantRepositoryImpl)` and `access_service = providers.Factory(AccessService, role_grant_repository=role_grant_repository)`; add `"core.http.permissions"` to `wiring_config.modules`
- [X] T012 [P] Create `server/core/tests/fakes.py` with `class FakeRoleGrantRepository` (constructor takes `role_names` and `codenames`, returns them in `role_grants`), and `server/core/tests/unit/test_access_service.py`: roles returned in declaration order even if the repository returns `["media", "leader"]`; Admin with no codenames → OWNER everywhere; Leader codenames → Leader column; no role → empty roles and levels
- [X] T013 [P] Create `server/core/tests/integration/test_access_repository.py` (`@pytest.mark.django_db`): a user in `leader` gets `["leader"]` and the 7 codenames; a superuser (`is_superuser=True`, `is_staff=True`) in no group gets nothing; a user in an extra group `"editors"` holding `members__owner` gets nothing; a user with `members__owner` in `user_permissions` directly gets nothing; a user in `leader` whose group also holds `auth.view_user` gets only `core.panelscope` codenames
- [X] T014 In `server/core/http/permissions.py` add, next to `IsAdminUser` (which stays for now): module-level `@inject def _grants_for(user_id: UUID, access_service: AccessService = Provide[Container.access_service]) -> AccessGrantsDTO` (module level so `dependency-injector` wiring patches it; a method on a class built later by the factory would not be wired); `def scope_permission(scope: Scope, overrides: Mapping[str, Level] | None = None) -> type[BasePermission]` that copies overrides into a `MappingProxyType`, calls `validate_overrides` (import-time failure, research R-05), and returns a `BasePermission` subclass with `message = "Você não tem permissão para esta ação."` whose `has_permission` returns `False` for an anonymous user and otherwise `_grants_for(request.user.pk).allows(scope, required_level(request.method, overrides))`; set the class `__name__`/`__qualname__` to `f"ScopePermission_{scope.name}"` for readable tracebacks. Docstring on `scope_permission` with the two usage examples from research R-04
- [X] T015 [P] Create `server/core/tests/unit/test_scope_permission.py`: replace the module-level `_grants_for` with `monkeypatch` by a function backed by `AccessService(FakeRoleGrantRepository(...))` (the container instance is built in `AccountsConfig.ready` and not reachable for `override`); for `scope_permission(Scope.MEMBERS)`: Leader passes GET/POST/PUT/PATCH and fails DELETE; Media fails GET; anonymous user (`is_authenticated=False`) fails without calling the repository; `scope_permission(Scope.REPORTS_HYMNAL_HISTORY, {"PATCH": Level.OWNER})` fails PATCH for Leader and passes for Admin; building `scope_permission(Scope.SONGS, {"DELETE": Level.VIEW})` raises `ValueError`
- [X] T016 In `server/conftest.py` add `make_role_client(*roles: Role, username: str = "role_user") -> tuple[APIClient, User]` that creates the user and adds `Group.objects.get(name=role.value)` for each role (groups come from migration 0005); change `make_admin_client` to also add the Admin group while still setting `profile.is_admin = True` (transition: both checks pass until Phase 8). Docstring on `make_role_client` with an example
- [X] T017 Create `server/core/tests/integration/test_management_access_matrix.py` with the scaffold every endpoint phase fills: a list `ENDPOINTS` of `(method, url, scope, required_level)` rows (start empty with a comment pointing to spec.md, Endpoint Classification), a `CALLERS` table `{"admin": [Role.ADMIN], "leader": [Role.LEADER], "media": [Role.MEDIA], "none": [], "leader+media": [Role.LEADER, Role.MEDIA]}` plus a superuser-without-role caller, and one parametrised test over `ENDPOINTS × CALLERS` that sends the request (empty JSON body, `format="json"`; IDs from a created fixture where the URL needs one) and asserts `status == 403` exactly when the caller's expected level (computed from the spec matrix written as a literal table in the test) is below `required_level`, and `status not in (401, 403)` otherwise. Plus one test: unauthenticated request to each row → 401

**Checkpoint**: Roles seeded with the matrix, levels readable, permission factory tested; no endpoint changed yet.

---

## Phase 3: User Story 1 - Administrator keeps full control (Priority: P1) 🎯 MVP

**Goal**: Everyone with `is_admin=True` becomes an Admin role holder; Admin reaches every scope.

**Independent Test**: Migrate a database with one `is_admin=True` and one `is_admin=False` profile;
the first is in group `admin`, the second in no group (spec US1 scenarios 1-2). Scenarios 3-5 are
covered by T004, T008 and the Admin rows of the access matrix as endpoints switch.

- [X] T018 [US1] Create hand-written `server/features/accounts/migrations/0003_is_admin_to_admin_role.py` depending on `("accounts", "0002_remove_profile_active")` and `("core", "0005_seed_panel_roles")`. Top docstring (CLAUDE.md §5): reason — `is_admin` is replaced by the Admin role (spec 012); what — every user whose profile has `is_admin=True` joins group `admin` in one bulk insert through `User.groups.through`, `ignore_conflicts=True`; irreversible on purpose (the requester dropped the rollback; a no-op reverse would let a rollback silently re-add `is_admin` as `False` for everyone — recovery is the pre-deploy dump); verified against a restored production dump (quickstart §3). `operations = [migrations.RunPython(forward)]` with no `reverse_code`
- [X] T019 [US1] Create `server/features/accounts/tests/integration/test_is_admin_conversion_migration.py` following `server/features/members/tests/integration/test_birth_date_split_migration.py` (`@pytest.mark.django_db(transaction=True)`, fake-unapply technique: migrate to the conversion, fake back to `0002`, restore the leaf after): through the historical models create one user with `is_admin=True` and one with `False` (profiles via the historical `Profile`, not the signal), apply `0003`, assert the first is in group `admin` and the second in no group; a second test asserts migrating back raises `IrreversibleError`
- [X] T020 [US1] Add a test to `server/core/tests/integration/test_management_access_matrix.py` asserting that a user in group `admin` whose group has **no** permission rows (clear `group.permissions` in the test) still passes a `DELETE` row of the matrix — spec: Admin without stored permissions (depends on at least one DELETE row existing; add it together with T022 if run in order)

**Checkpoint**: Current admins are Admin role holders; nothing else changed.

---

## Phase 4: User Story 2 - Leader manages everything but cannot delete (Priority: P1)

**Goal**: Every management endpoint checks scope and level; Leader gets `manage`/`view`, never
`owner`.

**Independent Test**: As a Leader-only user, call every classified endpoint: reads and writes
pass, every DELETE and every hymnal configuration write is 403 (spec US2 scenarios 1-5).

Each of T021-T024 is its own commit: view switch + its rows in the access matrix + existing
tests still green (they use `make_admin_client`, which now satisfies both checks).

- [X] T021 [US2] Members: in `server/features/members/views/admin_members.py`, `admin_member_photo.py` and `admin_member_history.py` replace `IsAdminUser` with `scope_permission(Scope.MEMBERS)` keeping `IsAuthenticated` first; update the module docstring of `admin_members.py` ("Leader = `Profile.is_admin`…" → "Access: scope `members`; level by method (spec 012)") and the class docstring of `AdminMemberPhotoAPIView` ("leaders" → "`view` on `members`"). Add the 9 members rows of spec.md's classification to `ENDPOINTS` in `server/core/tests/integration/test_management_access_matrix.py`. In `server/features/members/tests/integration/test_admin_members_api.py` add: Leader PATCH changing `status` → 200 (US2 scenario 1), Leader DELETE member → 403 and the member still exists (scenario 2); in `test_admin_member_photo_api.py` Leader PUT → 200, Leader DELETE → 403
- [X] T022 [P] [US2] Schedule: in `server/features/schedule/views/schedule.py` set `permission_classes = [IsAuthenticated, scope_permission(Scope.SCHEDULE)]` on `MonthlySchedulePreviewAPI` and `MonthlyScheduleSaveAPI`; leave `CurrentMonthlyScheduleAPI` on `IsMemberUser`; comment on the preview view: POST that persists nothing, still `manage` by method (spec classification). Add the 2 rows to `ENDPOINTS`; in `server/features/schedule/tests/integration/test_schedule_views.py` add Leader save → 200 (US2 scenario 3)
- [X] T023 [P] [US2] Songs: in `server/features/songs/views/songs.py` `ChordChartListAPI.get_permissions` / `LyricsListAPI.get_permissions` return `[IsAuthenticated(), scope_permission(Scope.SONGS)()]` for POST (GET stays `AllowAny`), and `ChordChartDetailAPI` / `LyricsDetailAPI` use `[IsAuthenticated, scope_permission(Scope.SONGS)]`; in `server/features/songs/views/register_plays.py` the same on `RegisterSundayPlaysAPI` and its docstring "admin profile" → "`manage` on `songs`". Add the 5 rows to `ENDPOINTS`; in `server/features/songs/tests/integration/test_register_plays_api.py` add Leader register → 201 and in `test_chord_charts_lyrics_api.py` Leader POST/PATCH → 201/200; assert public GETs still answer anonymous callers
- [X] T024 [P] [US2] Hymnal history: in `server/features/songs/views/hymnal_history.py` `HymnalHistoryOccurrencesAPI` and `HymnalHistoryTopHymnsAPI` use `[IsAuthenticated, scope_permission(Scope.REPORTS_HYMNAL_HISTORY)]`; `HymnalHistorySettingsAPI.get_permissions` returns `[IsAuthenticated(), scope_permission(Scope.REPORTS_HYMNAL_HISTORY, {"PATCH": Level.OWNER})()]` for PATCH (GET stays `AllowAny`); `ServiceWindowListCreateAPI` uses `scope_permission(Scope.REPORTS_HYMNAL_HISTORY, {"POST": Level.OWNER})` and `ServiceWindowDetailAPI` `scope_permission(Scope.REPORTS_HYMNAL_HISTORY, {"PATCH": Level.OWNER})` (DELETE is already OWNER by default); a module-level constant for the scope and a comment: configuration writes are owner-only by override, reads are `view` (spec classification, clarification Q1). Update the module docstring ("Everything else is admin-only" → scope/level wording). Add the 8 rows to `ENDPOINTS`; in `server/features/songs/tests/integration/test_hymnal_history_admin_api.py` add Leader PATCH settings → 403 and Admin → 200 (request's override test), Leader GET service windows → 200, Leader POST window → 403; in `test_hymnal_history_reports_api.py` Leader and Media GET occurrences/top-hymns → 200
- [X] T025 [US2] In `server/core/tests/integration/test_management_access_matrix.py` add an explicit test (not only the parametrised one) that iterates every `ENDPOINTS` row with method `DELETE` and asserts 403 for a Leader-only caller, and asserts at least one such row exists (request: "LEADER recebe 403 em todo DELETE")

**Checkpoint**: No management view reads `is_admin` any more; Leader behaves per matrix.

---

## Phase 5: User Story 3 - Media team is kept away from the roll (Priority: P2)

**Goal**: Media gets no members endpoint and no `members/` file; `members/` follows `view` on `members`.

**Independent Test**: As a Media-only user, member endpoints and a `members/` file → 403; hymnal
report → 200 (spec US3).

- [X] T026 [US3] In `server/features/media/domain/media_rules.py` rename `MediaAudience.LEADER` to `MediaAudience.MEMBERS_SCOPE` (value `"members_scope"`) and update the `FOLDER_RULES` comment ("readable with `view` on `members`, spec 012"); in `server/features/media/dtos/media_dtos.py` rename `is_leader` to `can_view_members` (docstring example too); in `server/features/media/services/media_access_service.py` `_viewer_in_audience` reads `viewer.can_view_members`; in `server/features/media/views/media_file.py` build it with `scope_permission(Scope.MEMBERS)().has_permission(request, self)` and drop the `IsAdminUser` import. Update `server/features/media/tests/unit/test_media_access_service.py` and `test_media_rules.py` to the new names (class `TestLeaderFolder` → `TestMembersFolder`)
- [X] T027 [US3] In `server/features/media/tests/integration/test_media_file_api.py` make the `members/` tests role-based with `make_role_client`: Admin → served, Leader → served (US2 scenario 6), Media → 403, member without role → 403, superuser without role → 403 (contracts/management-access.md table); keep the existing "leader who is not a member" case as "Leader without membership → served"
- [X] T028 [P] [US3] In `server/features/members/tests/integration/test_admin_members_api.py` add: Media GET `api/admin/members/` → 403 and GET one member → 403 (US3 scenarios 1); schedule/songs 403 for Media is already covered by the matrix rows (scenario 3) and reports 200 by T024 (scenario 4)

**Checkpoint**: Media reaches nothing sensitive.

---

## Phase 6: User Story 4 - The app knows what to show (Priority: P2)

**Goal**: `GET/PATCH api/me/profile/` return `roles` and `permissions` per contracts/profile-api.md.

**Independent Test**: Read the profile as Admin, Leader, Media, Leader+Media, no role and
superuser without role; compare with the contract table.

- [X] T029 [US4] In `server/features/accounts/serializers/serializers.py` add to `ProfileSerializer` two read-only `SerializerMethodField`s, `roles` and `permissions`, reading an `AccessGrantsDTO` from `self.context["access_grants"]` (raise `KeyError` with a message naming the missing key and the expected type if absent — a silent default would hide a view that forgot it): `roles` → `[{"id": r.value, "name": ROLE_DISPLAY_NAMES[r]}]`; `permissions` → `{scope.value: level.wire_name if (level := grants.level_for(scope)) else None}` for every `Scope`; add both to `Meta.fields` and `read_only_fields`. Keep `is_admin` in the fields until T034
- [X] T030 [US4] In `server/features/accounts/views/profile.py` inject `access_service: AccessService = Provide[Container.access_service]` into `MeProfileAPIView.get` and `.patch` and pass `"access_grants": access_service.grants_for(user.pk)` in the serializer context (split a private helper if a method passes 20 lines)
- [X] T031 [P] [US4] In `server/features/accounts/tests/unit/test_profile_serializer.py` pass `access_grants` in every context; add: `roles`/`permissions` for a Media grants DTO (contract example), for an empty DTO (all 7 keys `null`), for Admin (all `"owner"`); `roles`/`permissions` in `data` are not in `validated_data`; missing `access_grants` raises `KeyError`
- [X] T032 [US4] In `server/features/accounts/tests/integration/test_profile_api.py` add: Leader profile lists `[{"id": "leader", "name": "Liderança"}]` and the Leader column (US4 scenario 1); Admin all `owner` (scenario 2); no role → `[]` and all `null` (scenario 3); Leader+Media → highest per scope (scenario 4); superuser without role → `[]`, all `null`; PATCH response carries the same two fields; adding a role and re-reading with the old ETag returns 200, not 304

**Checkpoint**: The app can decide what to show from one profile read.

---

## Phase 7: User Story 5 - Roles are assigned in the Django admin (Priority: P3)

**Goal**: Roles assignable in the Django admin; admin access stays independent.

**Independent Test**: Through the admin user form, add the Media role; the next request reflects it.

- [X] T033 [US5] (done in `server/core/tests/integration/test_role_assignment.py`, groups changed on the user as the admin form does) Add: the registered `User` admin exposes `groups` in one of its fieldsets (the existing `BaseUserAdmin.fieldsets` does — this pins it); `Group` is registered; and an integration test that saves a user's groups through `admin.site._registry[User]` change form (or `client.post` as a superuser to the change URL) and then that user's `GET api/admin/members/` goes from 403 (no role) to 200 (after adding `leader`) without a new login (US5 scenario 1, spec edge case "role removed while the app is open" in reverse); and that adding `admin` to a user leaves `is_staff` `False` (scenario 2, FR-027)

**Checkpoint**: All user stories functional.

---

## Phase 8: Polish & Cross-Cutting Concerns

- [X] T034 Remove the flag, one commit: in `server/features/accounts/models/profile.py` delete `is_admin`; run `python manage.py makemigrations accounts` → keep the generated `server/features/accounts/migrations/0004_*.py` (`RemoveField`) unedited and check it depends on `0003_is_admin_to_admin_role`; in `server/features/accounts/serializers/serializers.py` drop `is_admin` from `fields` and `read_only_fields`; in `server/core/http/permissions.py` delete `IsAdminUser`; in `server/conftest.py` stop setting `profile.is_admin` in `make_admin_client` (it becomes `make_role_client(Role.ADMIN, username="admin_user")`); in `server/features/accounts/tests/unit/test_permissions.py` delete `TestIsAdminUser` and drop `IsAdminUser()` from the no-profile parametrisation; in `server/features/accounts/tests/unit/test_profile_serializer.py` and `server/features/accounts/tests/integration/test_profile_api.py` replace the `is_admin` read-only tests with "`is_admin` is absent from the response and ignored in PATCH" (FR-021); fix every remaining `is_admin` in tests (`core/tests/integration/test_service_deletion_api.py`, `features/accounts/tests/integration/test_malformed_body_api.py`, `features/songs/tests/integration/test_hymnal_history_seed.py`, others found by the grep)
- [X] T035 Run quickstart §2 (grep for `is_admin|IsAdminUser|is_leader` in `server/`): matches only in `features/accounts/migrations/0001_initial.py`, `0003_…`, `0004_…`. Also grep for a bare `"media"` / `'media'` role string outside `core/domain/access.py` and migrations: none (spec, Roles)
- [X] T036 Run `python manage.py makemigrations --check --dry-run`, then quickstart §1 (`pytest`, `mypy .`, `ruff check .`) — all green
- [ ] T037 Run quickstart §3 against a restored production dump: admins before = Admin members after, Leader 7 and Media 4 permissions, no `is_admin` column, second `migrate` a no-op. Record the date and result in the top docstrings of `core/migrations/0005_seed_panel_roles.py` and `accounts/migrations/0003_is_admin_to_admin_role.py`
- [ ] T038 Run quickstart §4 (manual walk-through on the dev server) and re-read spec.md, plan.md and the specs touched by T002 against the code; fix any drift in the same commit as the code it describes

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: none. T002 (specs) before any code commit
- **Foundational (Phase 2)**: after Setup; blocks every story
- **US1 (Phase 3)**: after Phase 2; T020 needs one DELETE row (T021 or T024)
- **US2 (Phase 4)**: after Phase 2; T025 after T021-T024
- **US3 (Phase 5)**: after Phase 2; T028 after T021
- **US4 (Phase 6)**: after Phase 2; independent of US1-US3
- **US5 (Phase 7)**: after T021 (uses a members endpoint)
- **Polish (Phase 8)**: T034 after **all** views and media are switched (T021-T024, T026) and after T018 (the conversion must land before the column goes); T035-T038 after T034

### Within Phase 2

T003 → T004 ∥ T005 → T006 → T007 → T008; T009 → T010 → T011 → T012 ∥ T013; T014 (needs T011) → T015; T016 (needs T007); T017 (needs T014, T016)

### Commit groups

- Each of T021, T022, T023, T024, T026+T027 is one commit (view + its tests + its matrix rows)
- T029+T030+T031+T032 one commit (serializer requires the context the view supplies)
- T034 one commit (model field, migration, serializer, permission class, conftest, tests)
- Everything else may be its own commit

### Parallel Opportunities

- Phase 2: T004 ∥ T005; T012 ∥ T013; T015 ∥ T016
- After Phase 2: US1 (T018-T019), US4 (T029-T032) and the endpoint switches T022, T023, T024 touch different files
- T028 and T031 are test-only

---

## Parallel Example: after Phase 2

```text
Developer A: T018 → T019                       (US1 conversion)
Developer B: T021 → T025 → T028                (members, Leader DELETE sweep, Media)
Developer C: T022, T023, T024                  (schedule, songs, hymnal history)
Developer D: T029 → T030 → T031, T032          (profile)
Then:        T026 → T027 → T033 → T020 → T034 → T035-T038
```

---

## Implementation Strategy

### MVP First

1. Phase 1-2 (specs, domain, seeded roles, access service, permission factory)
2. Phase 3 (US1) — current admins become Admin role holders
3. Phase 4 (US2) — every endpoint on scopes; Leader usable
4. **Stop and validate**: matrix test green for Admin/Leader/none; quickstart §4 steps 1-3

### Incremental Delivery

1. US3 moves media to the members scope (Media role becomes safe to hand out)
2. US4 exposes roles to the app (the app update depends on it)
3. US5 pins the Django admin path
4. Phase 8 removes `is_admin` and runs the production-dump check. Everything ships in one deploy
   with the app update (breaking `/profile` change accepted)

---

## Notes

- Role strings: always `Role.X`, never `"media"`/`"leader"` literals outside `core/domain/access.py`
  and the two data migrations (which freeze their literals on purpose).
- Never edit `core/0004` or `accounts/0004` by hand; `core/0005` and `accounts/0003` are the only
  hand-written migrations.
- Error messages carry the offending value and the expected shape (CLAUDE.md §8).
- Commit spec and code together (CLAUDE.md §6.2); T002 lands first.
