# Research: Member Access and Access Requests

## R-01 — Renaming `is_member` without losing values

- **Decision**: hand-written `accounts/0006_rename_is_member_member_access.py` with
  `migrations.RenameField("profile", "is_member", "member_access")`, reason at the top.
- **Rationale**: `makemigrations` run non-interactively turns a rename into `RemoveField` +
  `AddField(default=False)`, which silently revokes everyone's access. `RenameField` is an
  `ALTER TABLE … RENAME COLUMN` on PostgreSQL and SQLite, reversible by itself.
- **Compensating controls** (constitution §5): verified against a restored production dump and
  rolled back (`migrate accounts 0005`) before deploy — steps in quickstart.md.
- **Alternatives**: `db_column="is_member"` (rejected, Complexity Tracking).

## R-02 — Where "flag OR leadership role" is decided

- **Decision**: a pure rule in `core.domain.access`: `MEMBER_ACCESS_ROLES = {ADMIN, LEADER}` and
  `has_member_access(flag, roles)`. `HasMemberAccess` reads the profile flag and, only when it is
  false, the caller's roles through the same `_grants_for` the scope permission uses. `/me`
  computes `member_access` with the same function from the grants it already loads.
- **Rationale**: one rule, three callers (permission, `/me`, the "Perfis" `access_via_role` flag,
  which the repository computes with an `Exists` on the same role names). No query when the flag
  is set.
- **Alternatives**: a `Role.MEMBER` group (rejected by the requester: the app derives
  `canOpenPanel` from "has any role"); granting the flag to leaders by data migration (drifts).

## R-03 — Scope `profiles`

- **Decision**: `Scope.PROFILES = "profiles"`. Adding it changes `PanelScope.Meta.permissions`, so a
  generated `AlterModelOptions` migration follows, then a data migration that get-or-creates
  `profiles__manage` and adds it to the Liderança group (shape of `core/0008`). Mídia gets nothing,
  Admin is owner in code.
- **Rationale**: levels live in the role groups (spec 012 D-1); code cannot grant them.

## R-04 — 24 h limit and 429

- **Decision**: a domain rule over stored data, not a DRF throttle: the service reads the
  account's newest request `created_at`; if it is less than 24 h before `clock.now()`, it raises
  `AccessRequestRateLimitedError` (a new `RateLimitedError` base → 429) with
  `retry_after_seconds`. One pending per (account, type) is a conditional `UniqueConstraint`
  (`status = pending`); an `IntegrityError` on insert becomes `AccessRequestPendingError`.
- **Rationale**: DRF throttles live in the cache, reset on restart, and key per process; the rule
  is "one request per day", which the table already records. The constraint closes the race
  between the check and the insert.
- **Alternatives**: `UserRateThrottle` with `1/day` (fixed window per cache, not rolling, lost on
  restart).

## R-05 — Push payloads

- **Decision**: `PushMessage.date` becomes optional and three optional fields are added:
  `request_id`, `request_type`, `reason`; `as_data()` emits only the fields set. New types
  `access_request_created` (leaders), `access_request_approved`, `access_request_denied`
  (requester). Leaders = `AccessService.user_ids_with_level(PROFILES, MANAGE)` minus the requester.
  Sent after the write returns; `PushService` never raises.
- **Rationale**: reuses the registry and sender of spec 017 unchanged. The reason is the only free
  text and goes to its addressee only (spec Clarifications).

## R-06 — Roll data outside `/me`

- **Decision**: `GET api/me/member/` in `features/members`. The repository reads
  `Member.objects.filter(profile__user_id=user_id)` (reverse lookup by string; no import of
  accounts) with `select_related("role")` and `prefetch_related("ministries")`. Headers
  `Cache-Control: private, no-store`, `Vary: Authorization`, no ETag. 404 `MEMBER_NOT_LINKED`
  without a link. Permission `IsAuthenticated` only: it is the caller's own record.
- **Rationale**: the app snapshots `/me` to disk with its ETag; roll data is sensitive (LGPD
  art. 11) and must stay in memory on the phone.

## R-07 — Linking an account to a roll member from the panel

- **Decision**: `PATCH api/admin/profiles/{user_id}/` with `member_id` (int or null). The accounts
  repository checks existence through `apps.get_model("members", "Member")`, and turns the
  one-to-one's `IntegrityError` into `MemberAlreadyLinkedError` (409); an unknown id is a field
  error on `member_id`. The Django admin path stays.
- **Rationale**: same uniqueness the Django admin enforces (spec 015); string lookup keeps the
  features apart.

## R-08 — `/me` access state

- **Decision**: `AccessRequestService.access_state(user_id, flag, roles)` returns
  `MemberAccessStateDTO(member_access, access_status, data_correction_pending)` from one query on
  pending request types; the profile view puts it in the serializer context next to the grants.
  `is_member` and `member_access` are both `SerializerMethodField`s reading it.
- **Rationale**: no hidden default — the serializer refuses to render without it, like
  `access_grants`.

## R-09 — Deletion and references

- **Decision**: `AccessRequest.user` `CASCADE`; `AccessRequest.decided_by` `SET_NULL`. Both added
  to the table in `specs/accounts/spec.md`.
