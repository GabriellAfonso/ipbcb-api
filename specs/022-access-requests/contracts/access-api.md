# Contract: Member Access and Access Requests API

Base path `/ipbcb/`. Every endpoint requires `Authorization: Bearer <access>`. Errors are
`{"error_code", "detail"}` (`detail` a pt-BR string, shown as is); validation errors add
`field_errors`. No endpoint here returns or accepts an e-mail.

---

## GET / PATCH `api/me/profile/` — changed fields (additive)

```json
{
  "name": "Ana Souza",
  "is_member": true,
  "member_access": true,
  "access_status": "granted",
  "access_requests_blocked": false,
  "data_correction_pending": false,
  "member_id": 12,
  "...": "unchanged fields"
}
```

| Field | Type | Meaning |
|-------|------|---------|
| `member_access` | bool | Effective access to member content: the stored flag **or** the Admin/Liderança role |
| `is_member` | bool | Same value as `member_access`. Deprecated; kept for at least two app versions |
| `access_status` | `"granted"` \| `"pending"` \| `"none"` | App labels: Liberado / Aguardando / Não liberado |
| `access_requests_blocked` | bool | Hide "Pedir acesso" / "Solicitar correção"; show "Pedidos de acesso indisponíveis. Fale com a liderança." |
| `data_correction_pending` | bool | A correction request is waiting |

All read-only; sent in `PATCH` they are ignored. ETag/304 unchanged (the ETag covers them).

---

## POST `api/me/access-requests/` — create a request

```json
{ "type": "access", "message": "Sou membro desde 2010." }
```

- `type`: `access` | `data_correction` (required).
- `message`: optional for `access`, required for `data_correction`; trimmed; ≤ 1000 chars;
  blank = absent.

`201`:

```json
{
  "id": 41,
  "type": "access",
  "message": "Sou membro desde 2010.",
  "status": "pending",
  "created_at": "2026-10-21T13:05:00-03:00",
  "decided_by": null,
  "decided_at": null,
  "denial_reason": null
}
```

| Situation | Status | `error_code` |
|-----------|--------|--------------|
| Bad `type`, missing/too long `message` | 400 | `VALIDATION_ERROR` (`field_errors.type` / `.message`) |
| Account blocked | 403 | `ACCESS_REQUESTS_BLOCKED` |
| `access` while already granted | 409 | `MEMBER_ACCESS_ALREADY_GRANTED` |
| Same type already pending | 409 | `ACCESS_REQUEST_PENDING` |
| Any request in the last 24 h | 429 | `ACCESS_REQUEST_RATE_LIMITED` (+ `retry_after_seconds`) |

Checked in this order. Leaders get push `access_request_created`.

---

## GET `api/me/member/` — my roll data

Only the caller's own linked record. `Cache-Control: private, no-store`, `Vary: Authorization`,
no ETag: **keep in memory only**.

`200`:

```json
{
  "id": 12,
  "name": "Ana Souza",
  "role": "Diaconisa",
  "ministries": ["Louvor", "Infantil"],
  "birth_day": 14,
  "birth_month": 3,
  "birth_year": null,
  "baptism_date": "2001-05-20",
  "gender": "F"
}
```

`404 MEMBER_NOT_LINKED` when `member_id` is null.

---

## "Perfis" — management (scope `profiles`)

Admin `owner`, Liderança `manage`, Mídia none (`403 PERMISSION_DENIED`). GET needs `view`,
POST/PATCH `manage`. GET responses are `private` with ETag.

### Account resource

```json
{
  "id": "5b0e…-uuid",
  "name": "Ana Souza",
  "username": "ana",
  "photo_url": "https://…/ipbcb/media/profiles/ana/6f1c….jpg",
  "member_access": false,
  "access_via_role": false,
  "access_requests_blocked": false,
  "member": { "id": 12, "name": "Ana Souza" },
  "date_joined": "2025-03-14",
  "pending_requests": [ { "...": "request resource" } ]
}
```

`member_access` here is the **stored flag**; `access_via_role` says Admin/Liderança grants it
anyway (so revoking changes nothing for them). The detail adds `"requests": [...]`, the full
history newest first. Request resource as in `POST api/me/access-requests/`, plus `decided_by`
`{"id", "name"}` when decided.

### GET `api/admin/profiles/?status=pending|all`

`{"accounts": [...]}`. `pending` (Pendentes): accounts with a pending request, oldest pending
first. `all` (Todos, default): every active account, by name. Unknown `status` → 400.

### GET `api/admin/profiles/{user_id}/`

Account resource + `requests`. Unknown id → 404.

### PATCH `api/admin/profiles/{user_id}/`

```json
{ "access_requests_blocked": true, "member_id": 12 }
```

Both optional; `member_id: null` removes the link. Returns the detail. Errors:
`400 VALIDATION_ERROR` (`field_errors.member_id`, unknown member or unknown field),
`409 MEMBER_ALREADY_LINKED`, `404`.

### POST `api/admin/profiles/{user_id}/revoke-access/`

Clears the stored flag. No push. Returns the detail.

### POST `api/admin/profiles/requests/{request_id}/approve/`

`access`: sets the account's flag; `data_correction`: closes it ("resolvido"). Returns the
account detail. `409 ACCESS_REQUEST_NOT_PENDING`, `404`. Push `access_request_approved` to the
requester.

### POST `api/admin/profiles/requests/{request_id}/deny/`

```json
{ "reason": "Procure o pastor após o culto." }
```

`reason` optional, trimmed, ≤ 500 chars. Returns the account detail. Same errors. Push
`access_request_denied` to the requester.

---

## Push messages (data-only FCM, as spec 017)

| `type` | Extra keys | Recipients |
|--------|------------|------------|
| `access_request_created` | `request_id`, `request_type` | active accounts with `manage` on `profiles`, except the requester |
| `access_request_approved` | `request_id`, `request_type` | the requester |
| `access_request_denied` | `request_id`, `request_type`, `reason` (only when given) | the requester |

```json
{ "type": "access_request_denied", "request_id": "41", "request_type": "access", "reason": "…" }
```

All values strings. No name, roll field or e-mail. Revocation, block and link send nothing.
