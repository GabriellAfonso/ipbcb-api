# Contract: access to management endpoints

Which endpoint requires which scope and level: spec.md, Endpoint Classification (not repeated
here). This file fixes the responses.

## Order of checks

1. Authentication. No or invalid token → `401`, canonical shape, as today.
2. Scope level. Level below the required one → `403`:

   ```json
   {"error_code": "PERMISSION_DENIED", "detail": "Você não tem permissão para esta ação."}
   ```

3. Method dispatch. A method the endpoint does not implement → `405`, only reached by a caller
   with enough level on the scope. A caller with no level learns nothing about the endpoint.
4. Business logic, validation, not-found — unchanged.

## Media (`/ipbcb/media/members/…`)

Unchanged responses (`specs/009-protected-media-access/contracts/media-endpoint.md`); only the
audience changes: `view` on `members` instead of `is_admin`.

| Caller                         | `members/…` file |
|--------------------------------|------------------|
| Admin                          | served           |
| Leader                         | served           |
| Media                          | `403`            |
| Member without role            | `403`            |
| Superuser without role         | `403`            |
