# Data Model: Member Access and Access Requests

## Profile (accounts) — changed

| Field | Type | Notes |
|-------|------|-------|
| `member_access` | bool, default false | Renamed from `is_member` (values kept, R-01). The stored flag; effective access also counts the Admin/Liderança roles |
| `access_requests_blocked` | bool, default false | New. Leaders set it; a blocked account cannot create requests |
| `member` | OneToOne → `members.Member`, nullable, `SET_NULL` | Unchanged; now also writable from "Perfis" |

## AccessRequest (accounts) — new

| Field | Type | Notes |
|-------|------|-------|
| `id` | bigint PK | |
| `user` | FK → User, `CASCADE`, `related_name="access_requests"` | the requester |
| `type` | char(20): `access` \| `data_correction` | |
| `message` | text, nullable | ≤ 1000 chars after trim; required for `data_correction` |
| `status` | char(10): `pending` \| `approved` \| `denied`, default `pending`, indexed | |
| `decided_by` | FK → User, nullable, `SET_NULL`, `related_name="+"` | |
| `decided_at` | datetime, nullable | |
| `denial_reason` | text, nullable | ≤ 500 chars after trim; only on `denied` |
| `created_at` | datetime, `auto_now_add`, indexed | |

Constraints: `UniqueConstraint(fields=["user", "type"], condition=Q(status="pending"),
name="access_request_one_pending_per_type")`. `Meta.ordering = ["-created_at", "-id"]`.

### State transitions

```
pending ──approve──▶ approved   (access: sets Profile.member_access; data_correction: nothing)
pending ──deny─────▶ denied     (optional reason)
approved / denied: final (deciding again → 409 ACCESS_REQUEST_NOT_PENDING)
```

## Derived values

- `member_access` (effective) = `Profile.member_access` OR roles ∩ {Admin, Liderança} ≠ ∅.
- `access_status` = `granted` if effective access; else `pending` if a pending `access` request
  exists; else `none`.
- `data_correction_pending` = a pending `data_correction` request exists.
- Next request allowed at = newest `created_at` (any type, any status) + 24 h.

## DTOs (`features/accounts/dtos.py`)

| DTO | Fields |
|-----|--------|
| `AccessRequestCreateDTO` | type, message (None when blank) |
| `AccessRequestRecordDTO` | id, user_id, type, message, status, created_at, decided_by (`PersonRefDTO` \| None), decided_at, denial_reason |
| `PersonRefDTO` | id (UUID), name |
| `LinkedMemberDTO` | id, name |
| `ManagedAccountDTO` | id, name, username, photo_path, member_access (flag), access_via_role, access_requests_blocked, member (`LinkedMemberDTO` \| None), date_joined, pending_requests |
| `ManagedAccountPatchDTO` | access_requests_blocked?, member_id? (`model_fields_set` tells absent from null) |
| `MemberAccessStateDTO` | member_access, access_status, data_correction_pending |

## Own roll record (members) — read model

`OwnMemberRecordDTO`: id, name, role (str \| None), ministries (list[str], sorted), birth_day,
birth_month, birth_year, baptism_date, gender (`M` \| `F` \| None).

## Exceptions (`core/domain/access_request_exceptions.py`)

| Exception | Base → status | `error_code` | detail (pt-BR) |
|-----------|---------------|--------------|----------------|
| `AccessRequestsBlockedError` | PermissionDenied → 403 | `ACCESS_REQUESTS_BLOCKED` | "Pedidos de acesso indisponíveis. Fale com a liderança." |
| `MemberAccessAlreadyGrantedError` | Conflict → 409 | `MEMBER_ACCESS_ALREADY_GRANTED` | "Você já tem acesso de membro." |
| `AccessRequestPendingError` | Conflict → 409 | `ACCESS_REQUEST_PENDING` | "Você já tem um pedido aguardando resposta." |
| `AccessRequestRateLimitedError` | RateLimited → 429 | `ACCESS_REQUEST_RATE_LIMITED` | "Você já fez um pedido nas últimas 24 horas. Tente novamente mais tarde." + `retry_after_seconds` |
| `AccessRequestMessageRequiredError` | Validation → 400 | `VALIDATION_ERROR` | field `message` |
| `AccessRequestNotFoundError` | NotFound → 404 | `NOT_FOUND` | "Pedido não encontrado: id=…" |
| `AccessRequestNotPendingError` | Conflict → 409 | `ACCESS_REQUEST_NOT_PENDING` | "Este pedido já foi respondido." |
| `ManagedAccountNotFoundError` | NotFound → 404 | `NOT_FOUND` | "Conta não encontrada: id=…" |
| `RollMemberNotFoundError` | Validation → 400 | `VALIDATION_ERROR` | field `member_id` |
| `RollMemberAlreadyLinkedError` | Conflict → 409 | `MEMBER_ALREADY_LINKED` | "Este membro já está vinculado a outra conta." |
| `MemberNotLinkedError` | NotFound → 404 | `MEMBER_NOT_LINKED` | "Sua conta não está vinculada a um membro do rol." |
