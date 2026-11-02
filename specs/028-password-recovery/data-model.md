# Data Model: Password recovery by e-mail

Generated migration `accounts/0009`. No data migration: existing accounts start with no address.

## Profile (added fields)

| Field | Type | Notes |
|-------|------|-------|
| `recovery_email` | `EmailField`, blank, default `""`, indexed | Trimmed and lowercased. Not unique. Never a login, never read by Google sign-in |
| `recovery_email_confirmed_at` | `DateTimeField`, null | Null when not confirmed; cleared when the address changes |

## EmailCode (new)

A pending code. A row exists only while the code can still be used: consuming or invalidating it deletes the row.

| Field | Type | Notes |
|-------|------|-------|
| `user` | FK to User, `CASCADE`, `related_name="+"` | A pending code has no meaning without its account |
| `purpose` | `recovery` or `confirmation` | |
| `address` | `EmailField` | The address it was sent to |
| `code_digest` | `CharField(64)` | Keyed hash, research R-08 |
| `failed_attempts` | `PositiveSmallIntegerField`, default 0 | Shared by the live rows of an address for recovery, research R-01 |
| `expires_at` | `DateTimeField`, indexed | Created + 15 minutes |
| `created_at` | `DateTimeField`, auto | |

- Unique `(user, purpose)`: a new request replaces, so at most one per account and purpose.
- Index `(purpose, address)`: the recovery lookup.
- Not registered in the Django admin.

## EmailSendLedger (new)

| Field | Type | Notes |
|-------|------|-------|
| `address_key` | `CharField(64)`, unique | Keyed hash of the address, research R-04 |
| `send_times` | `JSONField`, default list | ISO instants inside the last hour |
| `updated_at` | `DateTimeField`, auto, indexed | The cleanup deletes rows untouched for an hour |

## Rules

- `MAX_WRONG_ATTEMPTS = 5`, `CODE_LIFETIME = 15 min`, `SEND_MIN_INTERVAL = 1 min`, `SEND_MAX_PER_HOUR = 5`.
- Recovery matches: `is_active`, `has_usable_password()`, `profile.recovery_email == address`.
- A recovery code is honoured only while its account still matches those three.

## DTOs

| DTO | Fields |
|-----|--------|
| `RegisterDTO` (changed) | adds required `recovery_email` |
| `RecoveryEmailChangeDTO` | `recovery_email`, `current_password` |
| `PasswordRecoveryRequestDTO` | `email` |
| `PasswordRecoveryConfirmDTO` | `email`, `code`, `new_password` |
| `EmailMessageDTO` | `to`, `subject`, `body` |
| `NewEmailCodeDTO` | `user_id`, `purpose`, `address`, `code_digest`, `expires_at` |
| `PendingEmailCodeDTO` | `user_id`, `code_digest` |
