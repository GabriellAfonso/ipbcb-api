# Implementation Plan: Password recovery by e-mail

**Branch**: `028-password-recovery` | **Date**: 2026-11-02 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/028-password-recovery/spec.md`

## Summary

`Profile` gains `recovery_email` and `recovery_email_confirmed_at`, separate from `User.email`, which only Google writes. That separation is what keeps Google sign-in safe. Registration requires the address. Two new services: `RecoveryEmailService` (set, send code, confirm, signed in) and `PasswordRecoveryService` (public request and confirm). Pending codes live in `EmailCode`, deleted when consumed; per-address send limits live in `EmailSendLedger`, keyed by a hash. Messages go through Django's SMTP backend to Brevo, in a background thread after commit. A management command in the daily loop removes expired rows.

## Technical Context

**Language/Version**: Python 3.14, `.venv_windows`

**Primary Dependencies**: Django, DRF, SimpleJWT, django-axes, dependency-injector, Pydantic. No new library.

**Storage**: PostgreSQL (SQLite in tests). One generated migration.

**Testing**: pytest, named fakes in `features/accounts/tests/fakes.py`, `django_capture_on_commit_callbacks`.

**Target Platform**: Linux container behind nginx; only client is the Android app.

**Project Type**: Web service.

**Performance Goals**: The request answers without waiting for delivery.

**Constraints**: No queue or Redis. No shared cache, so DRF throttles are per process: limits that must hold live in the database.

**Scale/Scope**: One congregation; far below the 300 messages per day of the provider's free plan.

## Constitution Check

| Rule | Status |
|------|--------|
| Every password check behind the lockout | Pass: setting the address uses `PasswordCheck` from the view. Recovery checks no password |
| Services take no HTTP object | Pass |
| Repositories alone touch the ORM | Pass. Services use `transaction.atomic`/`on_commit`, as `PasswordChangeService` and the gallery do |
| Input through serializers | Pass |
| No credentials in code | Pass: environment only |
| Error shape, `isinstance` mapping | Pass: new domain exceptions |
| Features do not import each other | Pass: all in `features/accounts` |
| Client IP through `NUM_PROXIES` | Pass: `ScopedRateThrottle` |
| Explicitly public endpoints | Pass: two endpoints, marked in the contract |
| Models have `__str__`, ordering, verbose name | Pass for the new models |
| **Amended**: a user-typed e-mail never identifies an account or links a sign-in | Added by this feature |

No Complexity Tracking entry is needed.

## Project Structure

```text
specs/028-password-recovery/   plan, research, data-model, contracts, quickstart, tasks
specs/accounts/spec.md         domain spec updated
specs/constitution.md          new rule

server/core/application/email_address.py              normaliser
server/core/application/dtos/{auth,account}_dtos.py   DTOs
server/core/domain/account_exceptions.py              new errors
server/config/{di.py, settings/*}                     wiring, e-mail settings, throttle scope
server/features/accounts/
├── domain/email_codes.py                 codes, hashing, limits (pure)
├── domain/email_messages.py              message text in Portuguese (pure)
├── models/email_code.py                  EmailCode, EmailSendLedger
├── repositories/email_code_repository.py
├── repositories/email_sender.py          SMTP sender and background wrapper
├── repositories/lockout_resetter.py      axes wrapper
├── services/recovery_email_service.py    signed-in
├── services/password_recovery_service.py public
├── serializers/recovery_serializers.py
├── views/recovery_email.py
├── views/password_recovery.py
└── management/commands/purge_expired_email_codes.py
compose.prod.yml, .env.example, http/auth.rest
```

**Structure Decision**: Everything stays in the accounts feature; only the normaliser and DTOs go in `core`, because `RegisterDTO` is there.

## Implementation order

1. Spec and constitution first (CLAUDE.md section 6.2).
2. Models, migration, normaliser, pure domain.
3. Repositories, sender, resetter.
4. Registration and profile fields.
5. Services, serializers, views, wiring.
6. Cleanup command and deployment files.
7. The Google invariant test and the SECURITY comment.

Research: [research.md](research.md). Model: [data-model.md](data-model.md). Contract: [contracts/recovery-api.md](contracts/recovery-api.md). Validation: [quickstart.md](quickstart.md).
