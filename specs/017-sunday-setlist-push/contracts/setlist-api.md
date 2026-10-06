# Contract: Setlist API

Base path `/ipbcb/`. All endpoints require a JWT. Every response depends on the caller's access
and is declared `Cache-Control: private, no-store` + `Vary: Authorization`. Errors use the
canonical `{"error_code", "detail"}` shape (spec 001).

`{date}` is `YYYY-MM-DD`. Dates in bodies are `YYYY-MM-DD`; `saved_at` is ISO 8601 with offset.

---

## Setlist object

```json
{
  "date": "2026-10-04",
  "items": [
    { "position": 1, "song_id": 12, "title": "Grande é o Senhor", "artist": "Adhemar de Campos", "tone": "G" },
    { "position": 2, "song_id": 55, "title": "Tu és fiel", "artist": "Fernandinho", "tone": "A#" }
  ],
  "saved_by_name": "Ana Paula",
  "saved_at": "2026-10-01T19:42:10-03:00"
}
```

`items` ordered by `position`. `saved_by_name` is `null` when the author account was deleted.

---

## PUT `api/setlists/{date}/` — save (create or replace)

- **Permission**: `manage` on `songs` **and** worship member.
- **Body**:
  ```json
  { "items": [ { "song_id": 12, "position": 1, "tone": "G" } ] }
  ```
- **Rules**: `{date}` is a Sunday; `items` non-empty list of objects; `song_id` integer;
  `position` integer 1–10, unique; `tone` string 1–3 characters after trimming; every song
  exists. A save for an existing date replaces every item.
- **Success**: `200` with the Setlist object as stored. A `setlist_saved` push follows
  ([push-messages.md](push-messages.md)); its outcome never changes this answer.

| Situation | Status | `error_code` |
|-----------|--------|--------------|
| No / invalid JWT | 401 | `NOT_AUTHENTICATED` / `AUTHENTICATION_FAILED` |
| No `manage` on `songs` | 403 | `PERMISSION_DENIED` |
| Not a worship member | 403 | `PERMISSION_DENIED` — "Disponível apenas para o ministério de Louvor." |
| Body not an object, `items` missing/empty/not a list, item not an object, bad `song_id`/`position`/`tone` | 400 | `VALIDATION_ERROR` |
| `{date}` not `YYYY-MM-DD` | 400 | `VALIDATION_ERROR` |
| `{date}` not a Sunday | 400 | `VALIDATION_ERROR` — names the date and weekday |
| Repeated position | 400 | `VALIDATION_ERROR` — names the positions |
| Song id not found | 404 | `NOT_FOUND`, `missing_song_ids: [...]` |

## GET `api/setlists/{date}/` — read by date

- **Permission**: `manage` on `songs` (`GET` override).
- **Success**: `200` Setlist object.
- **Errors**: `400` bad date format; `403`; `404` `NOT_FOUND` when no setlist for that date.
  Any date format-valid is accepted (a non-Sunday simply has no setlist → 404).

## DELETE `api/setlists/{date}/` — delete

- **Permission**: `manage` on `songs` **and** worship member — the same as saving. `DELETE`
  defaults to `owner`; the endpoint lowers it with `lowered={"DELETE"}` (spec 012, Lowered
  overrides).
- **Success**: `204`, no body. The setlist and its items are deleted; `Played` rows are not.
  No push is sent: the app re-reads `current/` on start and resume and treats
  `{"setlist": null}` as deleted.

| Situation | Status | `error_code` |
|-----------|--------|--------------|
| No / invalid JWT | 401 | `NOT_AUTHENTICATED` / `AUTHENTICATION_FAILED` |
| No `manage` on `songs` | 403 | `PERMISSION_DENIED` |
| Not a worship member | 403 | `PERMISSION_DENIED` — "Disponível apenas para o ministério de Louvor." |
| `{date}` not `YYYY-MM-DD` | 400 | `VALIDATION_ERROR` |
| No setlist for `{date}` | 404 | `NOT_FOUND` |

## GET `api/setlists/current/` — current setlist

- **Permission**: worship member (any role or none).
- **Success**: `200`
  ```json
  { "setlist": { ...Setlist object... } }
  ```
  or, when there is no setlist dated today or later (`America/Sao_Paulo`):
  ```json
  { "setlist": null }
  ```
- **Errors**: `403` not a worship member.

## GET `api/setlists/pending-confirmation/` — Sundays without registered plays

- **Permission**: `manage` on `songs` (`GET` override).
- **Success**: `200` — array of Setlist objects dated on or before today with no `Played` row for
  their date, newest first. Empty array when none.
- **Errors**: `403`.

Route order: `current/` and `pending-confirmation/` are declared before `{date}/`.
