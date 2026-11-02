# Tasks: Password recovery by e-mail

**Input**: Design documents from `specs/028-password-recovery/`

**Tests**: Required: CLAUDE.md section 10 asks a test for every new function, and the spec names a mandatory Google test.

Paths are relative to the repository root.

## Phase 1: Setup

- [X] T001 Add the rule "a user-typed e-mail never identifies an account or links a sign-in" to `specs/constitution.md`
- [X] T002 Update the domain spec with models, DTOs, endpoints, rules, errors and the deletion table in `specs/accounts/spec.md`
- [X] T003 [P] Add e-mail settings and the `password_recovery` throttle scope in `server/config/settings/base.py`, console backend in `server/config/settings/dev.py`, locmem and the scope in `server/config/settings/test.py`
- [X] T004 [P] Document the e-mail variables in `.env.example`

## Phase 2: Foundational

- [X] T005 Add `recovery_email` and `recovery_email_confirmed_at` to `server/features/accounts/models/profile.py`
- [X] T006 Create `EmailCode` and `EmailSendLedger` in `server/features/accounts/models/email_code.py`, export from `server/features/accounts/models/__init__.py`, generate `server/features/accounts/migrations/0009_*.py`
- [X] T007 [P] Create the normaliser in `server/core/application/email_address.py`
- [X] T008 [P] Create codes, hashing and limits in `server/features/accounts/domain/email_codes.py`, with tests in `server/features/accounts/tests/unit/test_email_codes.py`
- [X] T009 [P] Create message text in `server/features/accounts/domain/email_messages.py`, with tests in `server/features/accounts/tests/unit/test_email_messages.py`
- [X] T010 [P] Add `InvalidEmailCodeError`, `EmailCodeRateLimitedError`, `RecoveryEmailNotSetError`, `RecoveryEmailAlreadyConfirmedError` to `server/core/domain/account_exceptions.py`, re-export from `server/core/domain/exceptions.py`
- [X] T011 Add DTOs to `server/core/application/dtos/account_dtos.py` and `server/features/accounts/dtos.py`
- [X] T012 Add `EmailCodeRepository`, `EmailSender`, `AccountLockoutResetter` protocols and the new `UserRepository`/`ProfileRepository` methods to `server/features/accounts/repositories/interfaces.py`
- [X] T013 Implement `server/features/accounts/repositories/email_code_repository.py`, with tests in `server/features/accounts/tests/integration/test_email_code_repository.py`
- [X] T014 [P] Implement `SmtpEmailSender` and `BackgroundEmailSender` in `server/features/accounts/repositories/email_sender.py`, with tests in `server/features/accounts/tests/unit/test_email_sender.py`
- [X] T015 [P] Implement `AxesLockoutResetter` in `server/features/accounts/repositories/lockout_resetter.py`
- [X] T016 Add named fakes in `server/features/accounts/tests/fakes.py`

## Phase 3: User Story 2 - E-mail at registration (P1)

**Goal**: password registration requires the address. **Independent test**: register with and without it.

- [X] T017 [US2] Add `recovery_email` to `RegisterDTO` in `server/core/application/dtos/auth_dtos.py` and `RegisterSerializer` in `server/features/accounts/serializers/serializers.py`
- [X] T018 [US2] Store it in `UserRepositoryImpl.create` in `server/features/accounts/repositories/user_repository.py`
- [X] T019 [US2] Update `server/features/accounts/tests/integration/test_register_api.py`, `tests/unit/test_auth_dtos.py`, `tests/unit/test_register_service.py`, `tests/unit/test_register_serializer.py`, `tests/unit/test_user_repository.py` and every other test registering by API

## Phase 4: User Story 1 - Recover a forgotten password (P1)

**Goal**: request and confirm. **Independent test**: request, read the code from the message, reset, sign in.

- [X] T020 [US1] Implement `PasswordRecoveryService` in `server/features/accounts/services/password_recovery_service.py`, with tests in `server/features/accounts/tests/unit/test_password_recovery_service.py`
- [X] T021 [US1] Add serializers in `server/features/accounts/serializers/recovery_serializers.py`
- [X] T022 [US1] Add views in `server/features/accounts/views/password_recovery.py`, routes in `server/features/accounts/urls.py`, wiring in `server/config/di.py`
- [X] T023 [US1] Test end to end in `server/features/accounts/tests/integration/test_password_recovery_api.py`: generic answers, limits, shared addresses, attempts per address, revocation, lockout cleared

## Phase 5: User Story 4 - The e-mail never opens an account (P1)

**Goal**: the invariant, enforced by a test. **Independent test**: Google sign-in with another account's recovery e-mail.

- [X] T024 [US4] Update the SECURITY comment in `server/features/accounts/services/google_auth_service.py`
- [X] T025 [US4] Add the required tests in `server/features/accounts/tests/integration/test_recovery_email_not_a_login.py`

## Phase 6: User Story 3 - See, change and confirm (P2)

**Goal**: signed-in management. **Independent test**: change, request, confirm, read the profile.

- [X] T026 [US3] Add the read-only fields to `ProfileSerializer` in `server/features/accounts/serializers/serializers.py`
- [X] T027 [US3] Implement `RecoveryEmailService` in `server/features/accounts/services/recovery_email_service.py`, with tests in `server/features/accounts/tests/unit/test_recovery_email_service.py`
- [X] T028 [US3] Add views in `server/features/accounts/views/recovery_email.py`, routes in `server/features/accounts/urls.py`, wiring in `server/config/di.py`
- [X] T029 [US3] Make the fields read-only in `server/features/accounts/admin.py`
- [X] T030 [US3] Test end to end in `server/features/accounts/tests/integration/test_recovery_email_api.py`

## Phase 7: Polish

- [X] T031 Add the cleanup command in `server/features/accounts/management/commands/purge_expired_email_codes.py` with a test, and run it in the daily loop in `compose.prod.yml`
- [X] T032 [P] Add samples to `http/auth.rest`
- [X] T033 Run the pre-commit hooks (black, ruff, mypy, bandit) and the full test suite; confirm `makemigrations --check` is clean
- [X] T034 Update the status of `specs/028-password-recovery/spec.md` and the completed items of `specs/accounts/tasks.md`

## Dependencies

Setup, then Foundational, then the stories. US2 comes first because registration creates the data US1 and the tests use. US4 needs only the model and registration, and US3 needs the Foundational phase. T003 must precede any integration test.

## Parallel opportunities

Within Foundational: T007, T008, T009, T010, T014, T015. Within Setup: T003, T004.

## Implementation strategy

MVP: US2 + US1 + US4, which ship together: registration without recovery has no value, and recovery without the invariant is unsafe. US3 completes it for existing accounts and typos. All of it is released together, in the coordinated order in `quickstart.md`.
