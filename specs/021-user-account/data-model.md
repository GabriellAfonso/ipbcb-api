# Data Model: User Account

No schema change and no migration. This feature reads and deletes existing rows.

## Entities touched

| Entity | Fields read / written | Change |
|--------|----------------------|--------|
| `accounts.User` | `username`, `email`, `password`, `date_joined`, `is_superuser` | `password` replaced on change; row deleted on account deletion |
| `accounts.Profile` | `name`, `photo` | deleted with the user (CASCADE); photo file removed by the existing `post_delete` signal |
| `core.DeviceToken` | — | deleted with the user (CASCADE) |
| `token_blacklist.OutstandingToken` | `user`, `jti` | kept; `user` cleared by SimpleJWT's `SET_NULL` |
| `token_blacklist.BlacklistedToken` | `token` | one row created per outstanding, not-yet-blacklisted token of the user, on password change and on deletion |
| `members.Member` | — | never touched; loses its `profile` reverse link |

References kept with author cleared (`SET_NULL`, existing): gallery `Photo.uploaded_by`,
`PhotoTag.tagged_by`, `TrashEntry.deleted_by`; events `Event.created_by`; members
`MemberChangeLog.editor`; songs `Setlist.saved_by`, `HymnalViewEvent.user`. Django admin
`LogEntry.user` cascades (accepted, spec).

## DTOs (Pydantic, `core/application/dtos/account_dtos.py`)

| DTO | Fields | Used by |
|-----|--------|---------|
| `PasswordChangeDTO` | `current_password: str`, `new_password: str` | `PasswordChangeService` |
| `AccountDeletionDTO` | `password: str \| None`, `id_token: str \| None` | `AccountDeletionService.delete_confirmed` |

Both inherit `StrictBaseModel`. `TokenDTO` (existing) is the password-change result.

## Derived profile fields

| Field | Rule |
|-------|------|
| `has_password` | `user.has_usable_password()` |
| `date_joined` | `localtime(user.date_joined, America/Sao_Paulo).date().isoformat()` |
| `username` | `user.username` |

## Domain exceptions (`core/domain/account_exceptions.py`)

| Exception | Base | `error_code` | HTTP |
|-----------|------|--------------|------|
| `InvalidPasswordError` | `ValidationError` | `INVALID_PASSWORD` | 400 |
| `PasswordNotSetError` | `ConflictError` | `PASSWORD_NOT_SET` | 409 |
| `ConfirmationMethodError` | `ValidationError` | `VALIDATION_ERROR` | 400 |
| `InvalidGoogleConfirmationError` | `ValidationError` | `INVALID_GOOGLE_TOKEN` | 400 |
| `GoogleAccountMismatchError` | `PermissionDeniedError` | `GOOGLE_ACCOUNT_MISMATCH` | 403 |
| `AccountDeletionBlockedError` | `ConflictError` | `ACCOUNT_DELETION_BLOCKED` | 409 |

## State transitions

```
password change:  has password ──(current ok)──▶ new password; all refresh tokens blacklisted; new pair issued
                  no password  ──▶ PASSWORD_NOT_SET (no change)
deletion:         active ──(confirmed, not superuser)──▶ gone (tokens blacklisted, rows deleted)
                  superuser ──▶ ACCOUNT_DELETION_BLOCKED (no change)
```
