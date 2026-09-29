# Contract: `api/me/profile/`

Only the fields that change. Everything else (auth, ETag, `private` caching, `photo_url`,
PATCH of `name`) is as in `specs/accounts/spec.md`.

## GET `api/me/profile/` — 200

```json
{
  "name": "Ana Paula",
  "is_member": true,
  "photo_url": "https://…/ipbcb/media/profiles/ana.paula/6f1c2d.png",
  "roles": [
    {"id": "leader", "name": "Liderança"},
    {"id": "media", "name": "Mídia"}
  ],
  "permissions": {
    "members": "manage",
    "schedule": "manage",
    "songs": "manage",
    "gallery": "manage",
    "events": "manage",
    "notices": "manage",
    "reports.hymnal_history": "view"
  }
}
```

| Field         | Type                                            | Rule |
|---------------|-------------------------------------------------|------|
| `is_admin`    | —                                               | **Removed.** Breaking change, accepted: the app ships with this feature |
| `roles`       | array of `{id, name}`                           | `id` ∈ `admin`, `leader`, `media`; `name` is the pt-BR display name. Ordered Admin, Leader, Media. Empty array for no role |
| `permissions` | object, one key per scope, always all 7 keys    | Value `"view"`, `"manage"`, `"owner"`, or `null` for no access. Admin: every value `"owner"` |

The app shows the management panel when `roles` is non-empty and hides actions whose scope level
is below what the endpoint requires (spec, Endpoint Classification). The backend check is the
only authority.

### Examples

| User                      | `roles`                        | `permissions`                                                  |
|---------------------------|--------------------------------|----------------------------------------------------------------|
| No role                   | `[]`                           | every key `null`                                               |
| Admin                     | `[admin]`                      | every key `"owner"`                                            |
| Media only                | `[media]`                      | `gallery`/`events`/`notices` `"manage"`, `reports.hymnal_history` `"view"`, rest `null` |
| Superuser, no role        | `[]`                           | every key `null`                                               |

## PATCH `api/me/profile/` — 200

Response body identical to GET. `roles` and `permissions` are read-only: sending them is ignored,
like `is_member` today.
