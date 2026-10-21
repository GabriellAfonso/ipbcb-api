# Contract: User Account API

Base path `/ipbcb/`. Every error is `{"error_code", "detail"}` (`detail` a pt-BR string, shown as
is); validation errors add `field_errors`. All endpoints below except the web page require
`Authorization: Bearer <access>`.

---

## GET / PATCH `api/me/profile/` — new fields (additive)

```json
{
  "name": "Ana Souza",
  "is_member": true,
  "photo_url": "https://…/ipbcb/media/profiles/ana/6f1c….jpg",
  "roles": [],
  "permissions": { "...": null },
  "member_id": 12,
  "is_worship_member": false,
  "can_save_setlist": false,
  "username": "ana",
  "has_password": true,
  "date_joined": "2025-03-14"
}
```

| Field | Type | Meaning |
|-------|------|---------|
| `username` | string | Login name (lowercase). Read-only |
| `has_password` | bool | The **account** has a usable password. Created by Google sign-in → `false`. Decides whether to offer "Trocar senha" and which confirmation deletion asks for. Read-only |
| `date_joined` | string `YYYY-MM-DD` | Account creation date in `America/Sao_Paulo`. Read-only |

Read-only fields sent in `PATCH` are ignored. ETag/304 unchanged (the ETag covers the new fields).

### PATCH body

`{"name": "…"}` — trimmed; empty/whitespace-only → `400 VALIDATION_ERROR`
(`field_errors.name`: "Este campo não pode ficar em branco."); more than 100 characters →
`400 VALIDATION_ERROR` ("O nome pode ter no máximo 100 caracteres.").

## DELETE `api/me/profile/photo/` — unchanged

`204`. Removes the reference and the file. No photo → still `204`.

---

## POST `api/me/password/` — change password

Throttle: scope `login` (10/min). Failed-attempt lockout like sign-in.

Request:

```json
{ "current_password": "…", "new_password": "…", "new_password_confirm": "…" }
```

Success `200`:

```json
{ "access": "<new access>", "refresh": "<new refresh>" }
```

> **The caller's current access token stops working immediately** (it carries a hash of the old
> password), and so does every refresh token the account held, on every device, **including this
> one**. The app MUST replace both stored tokens with the pair in this response before making
> any other request. Other devices get `401` on their next request and their refresh fails →
> they return to the login screen.

Errors (in the order they are checked):

| Situation | Status | `error_code` | `detail` |
|-----------|--------|--------------|----------|
| Missing field, new password < 6 chars, confirmation differs | 400 | `VALIDATION_ERROR` | `field_errors` with the registration messages ("A senha precisa ter ao menos 6 caracteres.", "As senhas não coincidem.", "Este campo é obrigatório.") |
| Account has no password (Google-only) | 409 | `PASSWORD_NOT_SET` | "Esta conta não tem senha." |
| Current password wrong | 400 | `INVALID_PASSWORD` | "Senha incorreta." |
| Too many wrong passwords (5 in 30 min, per username + address) | 429 | `ACCOUNT_LOCKED` | "Muitas tentativas de login. Tente novamente em 30 minutos." + `cooloff_seconds` |
| Throttle | 429 | `THROTTLED` | DRF message |
| No/invalid token | 401 | `NOT_AUTHENTICATED` / `AUTHENTICATION_FAILED` | — |

The new password may equal the old one (no reuse or complexity rule).

---

## POST `api/me/delete/` — delete my account

`POST` (not `DELETE`): the secret travels in the body, never in a URL. Throttle: scope `login`.
Lockout on the password path. Immediate and irreversible; the app asks the person to type
"EXCLUIR" first (UI only, not sent).

Request — the method depends on `has_password`:

```json
{ "password": "…" }
```

```json
{ "id_token": "<fresh Google ID token>" }
```

With a password the account must send `password` (`id_token` is ignored). Without one it must
send `id_token` (`password` is ignored). The `id_token` comes from a fresh Google sign-in in the
app, same client ID as `api/auth/google/`.

Success: `204`, empty body. The app then clears its tokens and returns to the signed-out
state (do **not** call `api/auth/logout/` or `api/me/devices/unregister/` — both are already done
and the access token no longer authenticates).

Deleted: the account, profile, profile photo file, push device tokens, role assignments; every
refresh token is blacklisted. Kept: the church roll record (`member_id` simply loses its link)
and everything the person authored (photos, tags, events, setlists, roll history), with no
author.

Errors (in the order they are checked):

| Situation | Status | `error_code` | `detail` |
|-----------|--------|--------------|----------|
| Body not a JSON object | 400 | `VALIDATION_ERROR` | — |
| Superuser account | 409 | `ACCOUNT_DELETION_BLOCKED` | "Esta conta não pode ser excluída pelo app. Fale com a liderança da igreja." |
| Account has a password, `password` missing/blank | 400 | `VALIDATION_ERROR` | "Esta conta tem senha: confirme com a senha." |
| Account has no password, `id_token` missing/blank | 400 | `VALIDATION_ERROR` | "Esta conta não tem senha: confirme com o Google." |
| Wrong password | 400 | `INVALID_PASSWORD` | "Senha incorreta." |
| Lockout | 429 | `ACCOUNT_LOCKED` | as above |
| Google token invalid, expired, wrong audience or e-mail not verified | 400 | `INVALID_GOOGLE_TOKEN` | "Não foi possível confirmar com o Google. Tente novamente." |
| Google token resolves to another account, or to none | 403 | `GOOGLE_ACCOUNT_MISMATCH` | "A conta Google não corresponde a esta conta." |
| Throttle | 429 | `THROTTLED` | — |
| No/invalid token (also: a retry after a successful deletion) | 401 | `NOT_AUTHENTICATED` / `AUTHENTICATION_FAILED` | — |

None of the confirmation failures is a `401`: the session is still valid.

---

## Web page `GET/POST conta/excluir/` (`https://<domain>/ipbcb/conta/excluir/`)

Public HTML page in pt-BR — the link for the Play Store listing. Not an API: no JSON.

- `GET` → explanation of what is deleted and kept; form "usuário + senha + confirmação"; Google
  button (when `GOOGLE_CLIENT_ID` is configured) for accounts without a password.
- `POST` (CSRF token required) with `method=password` (`username`, `password`, `confirm`) or
  `method=google` (`credential`, `confirm`).
- Outcomes: `200` success page; `200` form again with a message for a wrong username/password
  (generic), unticked confirmation, Google token problems, a Google account without a match, a
  password account using Google ("Esta conta tem senha; entre com usuário e senha."), a superuser;
  `429` page for lockout or throttle; `403` Django CSRF failure.
