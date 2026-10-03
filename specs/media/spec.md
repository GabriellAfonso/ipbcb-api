# Media Domain Spec

Serves user-uploaded files under `MEDIA_ROOT` only to callers allowed to read them. The public
URL stays `/ipbcb/media/<path>`; the backend decides by caller and top-level folder, and nginx
streams the bytes. Nothing under `MEDIA_ROOT` is public.

Introduced by `specs/009-protected-media-access/` (design, research, deploy order with the app
and nginx); folder audiences moved to roles by `specs/012-feature-role-permissions/`; trashed
gallery files by `specs/014-gallery-trash-sync/`.

---

## Data Models

None. Access is decided by folder and caller, never by a database record — except the one
gallery trash lookup below.

---

## Endpoint

### GET / HEAD `/ipbcb/media/<path>`

- `IsAuthenticated` (JWT, or session for the Django admin). Other methods: `405`.
- Throttle scope `media`, `3000/hour` per user, separate from the API quota.
- Allowed, production: `200`, empty body, `X-Accel-Redirect: /ipbcb/protected-media/<path>`
  (percent-encoded), `Content-Type` from the extension (see rule 6). nginx streams the file and
  answers `304` on revalidation.
- Allowed, `DEBUG=True`: `200` with the file bytes; same checks, same order.
- Both carry `Cache-Control: private, no-cache` and no `Vary: Authorization` — the constitution's
  media caching exception: the phone keeps the image but revalidates on every use, so a revoked
  membership takes effect on the next view.
- The route prefix is derived from `MEDIA_URL` minus `FORCE_SCRIPT_NAME`
  (`features/media/urls.py`), so it matches with and without nginx. `config/urls.py` has no
  `static(MEDIA_URL)` route, even in development.

---

## Folder Rules

| First segment | Who may read |
|---|---|
| `gallery`  | members (`Profile.is_member`). A file of a trashed photo or album: only `owner` on `gallery`, `404` to anyone else |
| `profiles` | members (any profile), or the photo's owner, member or not |
| `members`  | `view` on `members` (Admin, Liderança), membership not required |
| anything else, or no folder | nobody — `404` (default deny) |

Rules live in `FOLDER_RULES` (`features/media/domain/media_rules.py`). A new upload folder is
unreadable until a rule is added there.

---

## Business Rules

1. **Order of checks**: authentication, path validation, folder rule, caller's permission, (for
   `gallery/`) trash lookup, file existence. A caller outside a folder's audience gets `403`
   whether or not the file exists.
2. **Path validation never rewrites the path**: the string checked is the string sent to nginx.
   Rejected (`404`, no redirect): fewer than two segments; an empty, `.` or `..` segment (even
   one that stays inside `MEDIA_ROOT`); a backslash, `%`, NUL or control character. The file is
   located with symlinks resolved; anything resolving outside `MEDIA_ROOT`, or not a regular
   file, is "not found".
3. **Folder match is exact**: `gallery-old/`, `Gallery/` fall to default deny.
4. **Profile owner**: the caller owns `profiles/<folder>/<file>` when `<folder>` is their own
   photo folder (`features.accounts.validators.profile_photo_folder`: the username, or the user
   id for legacy usernames).
5. **Gallery trash** (`TrashedMediaLookup`, implemented by the gallery, wired in `config/di.py`):
   one indexed lookup from the stored name to its photo or album row. Skipped for a caller who
   is both member and `owner` on `gallery`. A non-member with `owner` reads trashed files only.
   A file no row references keeps the plain member rule.
6. **Content type** from a fixed allow-list by extension (`jpg`/`jpeg`, `png`, `webp`, `gif`),
   otherwise `application/octet-stream` — never Django's default `text/html`.
7. **Logging**: one `media_access` line per decision with `folder` and `outcome` (`allowed`,
   `forbidden`, `not_found`, `rejected`, `unruled`, `trashed`). The folder is logged only when
   it is a known, ruled folder; the rest of the path never is.

---

## Errors

| Scenario | Status | Domain exception |
|---|---|---|
| Not authenticated / invalid token | 401 | — (DRF) |
| Caller outside the folder's audience | 403 | `MediaAccessDeniedError` |
| Rejected path | 404 | `MediaPathRejectedError` |
| Folder without a rule | 404 | `MediaFolderNotRuledError` |
| File missing, not regular, or outside `MEDIA_ROOT` | 404 | `MediaFileNotFoundError` |
| Trashed gallery file, caller without `owner` | 404 | `MediaFileTrashedError` |
| Method other than GET/HEAD | 405 | — |
| Throttled | 429 | — |

All in `core/domain/exceptions.py`, mapped by the project's exception handler.

---

## Architecture

```
MediaFileAPIView                       builds MediaViewer from IsMemberUser,
  -> MediaAccessService                scope_permission(MEMBERS), scope_permission(GALLERY, owner)
      -> media_rules (pure)            path validation, folder rules, content type
      -> MediaFileRepository (Protocol) <- FilesystemMediaRepository
      -> TrashedMediaLookup (Protocol)  <- implemented in features/gallery
```

DTOs: `MediaViewer` (what the service knows about the caller), `MediaFile` (the authorized file).
Everything wired in `config/di.py`.

---

## Outside this repository

nginx (`nginx-deploy` repository) proxies `location /ipbcb/media/` to the backend and serves
`location /ipbcb/protected-media/ { internal; alias <media dir>/; }` without its own
`Cache-Control`/`Expires`, keeping `ETag`/`Last-Modified` and `X-Content-Type-Options: nosniff`.
Details and deploy order in `specs/009-protected-media-access/spec.md` (Dependencies).
