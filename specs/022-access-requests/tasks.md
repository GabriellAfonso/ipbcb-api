# Tasks: Member Access and Access Requests

**Input**: Design documents from `specs/022-access-requests/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/access-api.md

**Tests**: required (CLAUDE.md §10 — every new function gets a test; named fakes for I/O).
Paths below are relative to `server/` unless they start with `specs/`.

## Format: `[ID] [P?] [Story] Description`

## Phase 1: Setup

- [X] T001 Create `features/accounts/domain/__init__.py` (new package for pure rules)

## Phase 2: Foundational — rename and the member-access rule (blocks every story)

- [X] T002 Hand-written `features/accounts/migrations/0006_rename_is_member_member_access.py` (`RenameField`, reason and controls at the top, R-01); rename the model field in `features/accounts/models/profile.py`
- [X] T003 `MEMBER_ACCESS_ROLES`, `has_member_access(flag, roles)` and `Scope.PROFILES` in `core/domain/access.py`
- [X] T004 `HasMemberAccess` replaces `IsMemberUser` in `core/http/permissions.py` (flag, else roles via `_grants_for`)
- [X] T005 Replace every `IsMemberUser` / `is_member` caller: `features/events/views/public_events.py`, `features/gallery/views/{changes,gallery,permissions,tags}.py`, `features/media/{dtos/media_dtos.py,services/media_access_service.py,views/media_file.py}`, `features/members/views/{birthdays,members}.py`, `features/schedule/views/schedule.py`, `features/accounts/admin.py`, `conftest.py`, and the tests that set the flag
- [X] T006 Generated `core/migrations/0009_*` (PanelScope permissions with `profiles`) and hand-written data migration `core/migrations/0010_profiles_scope_for_leader.py` (Liderança `profiles__manage`)
- [X] T007 [P] Tests: `has_member_access` truth table in `features/accounts/tests/unit/test_access_request_domain.py`; scope count/matrix in the existing `core/tests/unit/test_access.py`, `core/tests/integration/test_panel_roles_seed.py`, `test_access_repository.py`, `test_management_access_matrix.py`; `HasMemberAccess` flag / Admin / Liderança / Mídia / no profile in `features/accounts/tests/unit/test_permissions.py`
- [X] T008 [P] Test: rename migration keeps values (forward and backward) in `features/accounts/tests/integration/test_member_access_rename_migration.py`
- [X] T009 `RateLimitedError` in `core/domain/base_exceptions.py` → 429 in `core/http/exceptions.py`; `core/domain/access_request_exceptions.py` (data-model.md table) re-exported from `core/domain/exceptions.py`; test in `features/accounts/tests/unit/test_access_request_domain.py`
- [X] T010 `access_requests_blocked` on `Profile`; `AccessRequest` model in `features/accounts/models/access_request.py`; generated `features/accounts/migrations/0007_*`
- [X] T011 Enums, limits and pure rules (`access_status`, `seconds_until_next_request`, `clean_text`) in `features/accounts/domain/access_requests.py`; DTOs in `features/accounts/dtos.py`; unit tests `features/accounts/tests/unit/test_access_request_domain.py`
- [X] T012 `AccessRequestRepository` Protocol + `AccessRequestRepositoryImpl` in `features/accounts/repositories/{interfaces,access_request_repository}.py`; integration tests `features/accounts/tests/integration/test_access_repositories.py`
- [X] T013 Push: three types in `core/domain/push.py`; optional fields in `core/application/dtos/push_dtos.py`; date-less logging in `core/application/push_service.py`; tests in `core/tests/unit/test_push_message.py`

## Phase 3: User Story 1 — Ask for access (P1) 🎯 MVP

- [X] T014 [US1] `AccessRequestService.create_request` (order of refusals FR-010, push to leaders) and `access_state` in `features/accounts/services/access_request_service.py`
- [X] T015 [P] [US1] Fakes `FakeAccessRequestRepository`, `FakeManagedAccountRepository`, `FakeRoleDirectory`, `RecordingPushNotifier`, `FixedClock` in `features/accounts/tests/access_fakes.py`; unit tests `features/accounts/tests/unit/test_access_request_service.py`
- [X] T016 [US1] `AccessRequestCreateSerializer` + record serializer in `features/accounts/serializers/access_request_serializers.py`; `MeAccessRequestAPIView` in `features/accounts/views/access_requests.py`; route `api/me/access-requests/`; DI
- [X] T017 [US1] Integration tests (contract table, race → 409, push to leaders only) in `features/accounts/tests/integration/test_access_request_api.py`

## Phase 4: User Story 2 — Leaders decide requests (P1)

- [X] T018 [US2] `ManagedAccountRepository` (list/get with roles `Exists`, pending requests in one query, set flag, set block, link member) in `features/accounts/repositories/managed_account_repository.py`; tests in `features/accounts/tests/integration/test_access_repositories.py` and through the API (T021, T023)
- [X] T019 [US2] `ProfileManagementService` (list, detail, approve, deny, push) in `features/accounts/services/profile_management_service.py`; unit tests on fakes `features/accounts/tests/unit/test_profile_management_service.py`
- [X] T020 [US2] Views `AdminProfileListAPIView`, `AdminProfileDetailAPIView`, `AdminAccessRequestDecisionAPIView` in `features/accounts/views/admin_profiles.py`; serializers; routes; DI
- [X] T021 [US2] Integration tests (Pendentes/Todos, approve access/data_correction, deny with reason, not pending, Mídia 403, push) in `features/accounts/tests/integration/test_admin_profiles_api.py`

## Phase 5: User Story 3 — Revoke, block, link (P2)

- [X] T022 [US3] Service `revoke_access`, `update_account` (block, link) and `POST …/revoke-access/`, `PATCH …/{user_id}/` in the same files as US2
- [X] T023 [US3] Integration tests (revoke → member endpoint 403, no push; block/unblock; link, conflict, unknown member, unlink) in `features/accounts/tests/integration/test_admin_profiles_manage_api.py`

## Phase 6: User Story 4 — Leaders reach member content (P2)

- [X] T024 [US4] Integration test: Liderança without flag reads schedule, members, birthdays, gallery; Mídia refused in `features/accounts/tests/integration/test_member_access_permission.py`

## Phase 7: User Story 5 — My roll data and corrections (P2)

- [X] T025 [US5] (unit test `features/members/tests/unit/test_member_service_own_record.py`) `OwnMemberRecordDTO`, `MemberRepositoryImpl.get_own_record`, `MemberService.get_own_record` (raises `MemberNotLinkedError`) in `features/members/…`
- [X] T026 [US5] `OwnMemberSerializer`, `OwnMemberAPIView` (`private, no-store`, `Vary`, no ETag) in `features/members/{serializers/own_member_serializer.py,views/own_member.py}`; route `api/me/member/`; DI wiring
- [X] T027 [US5] Tests: repository, linked/unlinked, headers, another member never returned in `features/members/tests/integration/test_own_member_api.py`

## Phase 8: User Story 6 — `/me` fields and compatibility (P3)

- [X] T028 [US6] `member_access`, `is_member`, `access_status`, `access_requests_blocked`, `data_correction_pending` in `ProfileSerializer`; `access_state` in the profile view context
- [X] T029 [US6] Tests in `features/accounts/tests/integration/test_member_access_permission.py` (flag, leader, Mídia, pending, PATCH ignores, ETag)

## Phase 9: Polish

- [X] T030 [P] `AccessRequest` and `access_requests_blocked` in the Django admin (`features/accounts/admin.py`)
- [X] T031 [P] Domain specs: `specs/accounts/spec.md`, `specs/members/spec.md`, `specs/{events,gallery,media,schedule}/spec.md`, `specs/012-feature-role-permissions/spec.md` (scope matrix, `profiles` endpoints, member access), constitution wording; `docs/features/{accounts,members}.md`
- [X] T032 Full suite, mypy, `makemigrations --check` (quickstart.md)
- [ ] T033 Verify the rename on a restored production dump and run the rollback (quickstart.md) — **manual, before deploy** (the forward/backward value check runs in `test_member_access_rename_migration.py` on the test database)

## Phase 10: Direct grant (US3, FR-017a/b)

- [X] T034 `Profile.access_granted_by` / `access_granted_at` (migration `accounts/0008`); grant record set on approval and direct grant, cleared on revoke (also in the Django admin)
- [X] T035 `ProfileManagementService.grant_access` (approves the pending `access` request, approval push) and `POST api/admin/profiles/{user_id}/grant-access/`; `access_granted_by` / `access_granted_at` in the account resource
- [X] T036 Tests: service on fakes, repository, API (no request, pending request, already flagged, Mídia refused, revoke clears the record)

## Dependencies

- Phase 2 blocks everything. US1 needs T009–T013. US2/US3 need US1's repository and the push
  types. US4 only needs Phase 2. US5 (roll data) is independent of requests except the
  `data_correction` type, already covered by US1. US6 needs T014.

## Implementation Strategy

Phase 2 first and keep the full suite green after the rename (it touches many features). Then
US1 → US2 → US3, US6, US5, US4 tests, Polish.
