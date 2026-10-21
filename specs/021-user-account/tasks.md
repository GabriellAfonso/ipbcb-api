# Tasks: User Account

**Input**: Design documents from `specs/021-user-account/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/account-api.md

**Tests**: required (CLAUDE.md §10 — every new function gets a test; named fakes for I/O).
Paths below are relative to `server/` unless they start with `specs/` or `docs/`.

## Format: `[ID] [P?] [Story] Description`

## Phase 1: Setup

- [ ] T001 Create `features/accounts/templates/accounts/` (template dir; `APP_DIRS` already on)

## Phase 2: Foundational (blocks every story)

- [ ] T002 [P] Add `InvalidPasswordError`, `PasswordNotSetError`, `ConfirmationMethodError`, `InvalidGoogleConfirmationError`, `GoogleAccountMismatchError`, `AccountDeletionBlockedError` with their `error_code`s and pt-BR messages (data-model.md) in `core/domain/account_exceptions.py`; re-export from `core/domain/exceptions.py`
- [ ] T003 [P] Add `PasswordChangeDTO` and `AccountDeletionDTO` (`StrictBaseModel`) in `core/application/dtos/account_dtos.py`
- [ ] T004 Add `set_password(user, raw)` and `delete(user)` to `UserRepository` (Protocol) and `UserRepositoryImpl` in `features/accounts/repositories/interfaces.py` and `user_repository.py`
- [ ] T005 Add `RefreshTokenRepository` Protocol and `RefreshTokenRepositoryImpl.revoke_all(user_id) -> int` (blacklists every outstanding, not-yet-blacklisted token) in `features/accounts/repositories/interfaces.py` and `refresh_token_repository.py`
- [ ] T006 Add `LoginService.authenticate_credentials(dto, request) -> User` (login reuses it) and `verify_password(user, password, request)` raising `InvalidPasswordError` in `features/accounts/services/login_service.py`
- [ ] T007 Add `GoogleAuthService.resolve_existing_account(token) -> User | None` (verify like sign-in, `get_by_email`, no creation) in `features/accounts/services/google_auth_service.py`
- [ ] T008 [P] Tests: exceptions map to the contract's status/code in `features/accounts/tests/unit/test_account_exceptions.py`
- [ ] T009 [P] Tests: `set_password`, `delete`, `revoke_all` (idempotent, other users untouched) in `features/accounts/tests/unit/test_user_repository.py` and `test_refresh_token_repository.py`
- [ ] T010 [P] Tests: `verify_password` right/wrong/other account, lockout after 5 failures (`AXES_ENABLED=True`) in `features/accounts/tests/integration/test_verify_password.py`
- [ ] T011 [P] Tests: `resolve_existing_account` found / not found / invalid / unverified in `features/accounts/tests/unit/test_google_auth_service.py`

## Phase 3: User Story 1 — Delete my account from the app (P1) 🎯 MVP

**Goal**: `POST api/me/delete/` per contract. **Independent test**: delete with password and with
Google; user, profile, photo file, device tokens gone; refresh tokens blacklisted; Member and
authored content kept.

- [ ] T012 [US1] `AccountDeletionService` (`delete_confirmed(user, dto, verify_password)`, `delete_authenticated(user)`, superuser block, method by `has_usable_password`, Google identity by pk) in `features/accounts/services/account_deletion_service.py`
- [ ] T013 [US1] `AccountDeletionSerializer` (`password`, `id_token`, both optional) in `features/accounts/serializers/serializers.py`
- [ ] T014 [US1] `AccountDeletionAPIView` (`IsAuthenticated`, `ScopedRateThrottle` `login`, `require_object_body`) in `features/accounts/views/account.py`; route `api/me/delete/` in `features/accounts/urls.py`
- [ ] T015 [US1] Register `refresh_token_repository`, `account_deletion_service`; wire `features.accounts.views.account` in `config/di.py`
- [ ] T016 [P] [US1] Fakes `FakeUserRepository`, `FakeRefreshTokenRepository`, `FakeGoogleAccountResolver` in `features/accounts/tests/fakes.py`; unit tests of the service order of checks in `features/accounts/tests/unit/test_account_deletion_service.py`
- [ ] T017 [US1] Integration tests for every row of the contract table, cascade/SET_NULL table (DeviceToken, Member, gallery Photo, Event, Setlist, MemberChangeLog), photo file removal, retry → 401, lockout in `features/accounts/tests/integration/test_account_deletion_api.py`

## Phase 4: User Story 2 — Delete my account through a web link (P1)

**Goal**: `conta/excluir/` page. **Independent test**: browser-like client with CSRF enforced
deletes with username+password and with a Google credential.

- [ ] T018 [US2] `mark_renders_own_lockout(response)` and the pass-through in `axes_lockout_response` in `core/http/lockout.py`; test in `core/tests/…/test_lockout.py` (existing lockout tests location)
- [ ] T019 [US2] `WebPasswordDeletionSerializer`, `WebGoogleDeletionSerializer` in `features/accounts/serializers/web_serializers.py`
- [ ] T020 [US2] `AccountDeletionPageView` (GET/POST, `never_cache`, COOP/Referrer headers, throttle, lockout page) and `AccountDeletionPageThrottle` in `features/accounts/views/account_deletion_page.py`; route `conta/excluir/` (name `account_deletion_page`); wiring in `config/di.py`
- [ ] T021 [US2] Template (pt-BR, what is deleted/kept, password form, GIS button only when `google_client_id`, outcomes) in `features/accounts/templates/accounts/account_deletion.html`
- [ ] T022 [US2] Integration tests: GET renders (with/without client id), CSRF missing → 403, password success/failure (generic message), unticked confirm, Google success/mismatch/password-account/invalid, superuser, lockout → 429 HTML, throttle → 429, headers in `features/accounts/tests/integration/test_account_deletion_page.py`

## Phase 5: User Story 3 — Change my password (P2)

**Goal**: `POST api/me/password/`. **Independent test**: two sessions; after change the caller's
new pair works, every old token fails.

- [ ] T023 [US3] Password field factory shared by `RegisterSerializer` and new `PasswordChangeSerializer` in `features/accounts/serializers/serializers.py`
- [ ] T024 [US3] `PasswordChangeService.change_password(user, dto, verify_password) -> TokenDTO` in `features/accounts/services/password_change_service.py`; DI provider in `config/di.py`
- [ ] T025 [US3] `PasswordChangeAPIView` in `features/accounts/views/account.py`; route `api/me/password/`
- [ ] T026 [P] [US3] Unit tests on fakes in `features/accounts/tests/unit/test_password_change_service.py`; serializer tests in `features/accounts/tests/unit/test_password_change_serializer.py`
- [ ] T027 [US3] Integration tests (contract table; old access/refresh of both sessions rejected; new pair works; lockout) in `features/accounts/tests/integration/test_password_change_api.py`

## Phase 6: User Story 4 — See my account details (P2)

- [ ] T028 [US4] `username`, `has_password`, `date_joined` read-only on `ProfileSerializer` in `features/accounts/serializers/serializers.py`
- [ ] T029 [US4] Tests: password vs Google account, date in `America/Sao_Paulo` across midnight UTC, PATCH ignores them in `features/accounts/tests/integration/test_profile_api.py`

## Phase 7: User Story 5 — Edit name and remove photo (P3)

- [ ] T030 [US5] `name`: `allow_blank=False`, pt-BR messages, max 100 in `features/accounts/serializers/serializers.py`
- [ ] T031 [US5] Tests: trim, blank, whitespace-only, 101 chars; photo DELETE removes the file in `features/accounts/tests/integration/test_profile_api.py`

## Phase 8: Polish

- [ ] T032 [P] Domain spec current state (fields, endpoints, page, rules, errors, architecture) in `specs/accounts/spec.md`
- [ ] T033 [P] Constitution amendments (LoginService exception; deletion web page) in `specs/constitution.md`
- [ ] T034 [P] Feature doc in `docs/features/accounts.md`
- [ ] T035 Run accounts + core tests, full suite, mypy, `makemigrations --check` (quickstart.md)

## Dependencies

- Phase 2 blocks everything. US1 needs T002–T007. US2 needs US1's service (T012). US3 needs
  T004–T006. US4/US5 are independent of the others.
- Commits: docs (spec/plan/tasks) first; then each story's code + tests + spec updates together.

## Parallel examples

- T002, T003 together; T008–T011 together after T004–T007.
- US4 and US5 can run alongside US3.

## Implementation Strategy

MVP = Phase 2 + US1 (in-app deletion), then US2 (the web link — both are needed for the Play
listing), then US3, US4, US5, Polish.
