# Contract: Device tokens and profile flags

Base path `/ipbcb/`. JWT required. Canonical error shape.

---

## POST `api/me/devices/` — register this device's push token

Call after every login and whenever the push provider rotates the token.

- **Body**: `{ "token": "<FCM registration token>" }`
- **Rules**: string, trimmed, 1–512 characters, no inner whitespace.
- **Success**: `204`. Idempotent. A token already registered by another account moves to the
  caller.
- **Errors**: `400` `VALIDATION_ERROR` (missing, not a string, empty, too long); `401`.

## POST `api/me/devices/unregister/` — forget this device's token

Call on logout **before** `POST api/auth/logout/`, while the access token is still valid.

- **Body**: `{ "token": "<FCM registration token>" }`
- **Success**: `204` always for a well-formed body — including an unknown token or one owned by
  another account (nothing is changed then).
- **Errors**: `400` malformed body; `401`.

The token is never placed in a URL: access logs would keep it.

---

## GET / PATCH `api/me/profile/` — two new read-only fields

```json
{
  "name": "Ana Paula",
  "is_member": true,
  "photo_url": null,
  "roles": [{ "id": "leader", "name": "Liderança" }],
  "permissions": { "members": "manage", "songs": "manage", "...": null },
  "member_id": 42,
  "is_worship_member": true,
  "can_save_setlist": true
}
```

| Field | Meaning |
|-------|---------|
| `is_worship_member` | linked member belongs to the "Louvor" ministry |
| `can_save_setlist` | `is_worship_member` **and** `manage` on `songs` |

Computed on every read; the ETag changes with them. Both are ignored on `PATCH`.
