# Contract: Recovery e-mail and password recovery

Base path `/ipbcb/`. Errors follow the canonical shape `{"error_code", "detail"}`; form errors carry `field_errors`.

## Changed

### POST `api/auth/register/`

New **required** field `recovery_email`. Missing, blank or invalid: 400 `VALIDATION_ERROR` with `field_errors.recovery_email` ("Este campo é obrigatório.", "Este campo não pode ficar em branco.", "Informe um e-mail válido."). The rest is unchanged. The address is not unique, so "e-mail já em uso" does not exist.

### GET/PATCH `api/me/profile/`

Two new read-only fields; a value sent in PATCH is ignored.

```json
{ "recovery_email": "ana@example.com", "recovery_email_confirmed": false }
```

`recovery_email` is `null` when the account has none. Both are returned for every account; for a Google-only account they are `null` and `false`.

## Public

Neither reads an `Authorization` header: an expired token must not break a signed-out flow.

### POST `api/auth/password-recovery/request/`

```json
{ "email": "ana@example.com" }
```

- **200**, always the same, whether or not anything matched and whether or not a limit was hit:
  `{"detail": "Se houver conta com esse e-mail, enviamos um código."}`
- 400 `VALIDATION_ERROR` only for a missing or malformed `email`, which says nothing about accounts.
- Client limit: scope `recovery_request`, 20/hour. Address limit: 1/minute and 5/hour. Past any limit the 200 stays and nothing is sent.

### POST `api/auth/password-recovery/confirm/`

```json
{ "email": "ana@example.com", "code": "123456", "new_password": "nova-senha", "new_password_confirm": "nova-senha" }
```

- **204**: the password changed, every token of the account was revoked, the lockout of the username was cleared. No tokens: the app returns to login.
- 400 `INVALID_EMAIL_CODE` "Código inválido ou expirado.": wrong, expired, used, or the attempt limit was reached.
- 400 `VALIDATION_ERROR` on `new_password` / `new_password_confirm`: same rules and messages as registration. Does not use the code or count as an attempt.
- Throttle scope `login`.

## Authenticated

All require `IsAuthenticated`, use throttle scope `login`, and answer 409 `PASSWORD_NOT_SET` for an account with no usable password.

### POST `api/me/recovery-email/`

```json
{ "recovery_email": "novo@example.com", "current_password": "secret1" }
```

- **200** `{"recovery_email": "novo@example.com", "recovery_email_confirmed": false}`. Sessions are kept.
- 400 `INVALID_PASSWORD` "Senha incorreta.". Counted by the lockout; 429 `ACCOUNT_LOCKED` once locked.
- 400 `VALIDATION_ERROR` on either field.
- The same address already stored is not a change: the confirmation and pending codes stay.

### POST `api/me/recovery-email/send-code/`

No body. Sends a code to the current address.

- **204**.
- 409 `RECOVERY_EMAIL_NOT_SET`, 409 `RECOVERY_EMAIL_ALREADY_CONFIRMED`.
- 429 `EMAIL_CODE_RATE_LIMITED` with `retry_after_seconds`.

### POST `api/me/recovery-email/confirm/`

```json
{ "code": "123456" }
```

- **200** `{"recovery_email": "ana@example.com", "recovery_email_confirmed": true}`.
- 400 `INVALID_EMAIL_CODE` "Código inválido ou expirado.".
