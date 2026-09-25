# Quickstart: Protected Media Access

How to prove the feature works. Contract: [contracts/media-endpoint.md](contracts/media-endpoint.md).
Types and decision order: [data-model.md](data-model.md).

---

## 1. Automated suite (Windows venv)

```powershell
cd server
..\.venv_windows\Scripts\python -m pytest features/media core/tests features/accounts/tests/unit/test_permissions.py -q
..\.venv_windows\Scripts\python -m pytest -q          # whole suite: nothing else regressed
..\.venv_windows\Scripts\python -m mypy .
```

Expected: all green. The media tests cover every case in spec SC-006: 401 unauthenticated,
403 non-member on `gallery/` and `profiles/`, 200 + `X-Accel-Redirect` + `private, no-cache`
for members, 403 non-leader / 200 leader on `members/`, 404 unruled folder, every traversal
form rejected with no redirect header, 404 missing file, file body under `DEBUG=True`.

## 2. Local development (`DEBUG=True`, no nginx)

```powershell
cd server
..\.venv_windows\Scripts\python manage.py runserver
```

With a file at `server/media/gallery/teste/foto.jpg`:

| Request | Expected |
|---------|----------|
| `curl -i http://127.0.0.1:8000/ipbcb/media/gallery/teste/foto.jpg` | `401` JSON |
| same, with `-H "Authorization: Bearer <member token>"` | `200`, `Content-Type: image/jpeg`, image bytes |
| `.../ipbcb/media/gallery/../gallery/teste/foto.jpg` with member token (`curl --path-as-is`) | `404` |

Nothing else under `/ipbcb/media/` is served without a token — the `static()` media route is gone.

## 3. Production, after the backend deploy but before the nginx switch

nginx still serves `/ipbcb/media/` from disk, so nothing reaches the new view. Images keep
working for old and new app versions. Nothing to check beyond the normal CD assertions.

## 4. Production, after the nginx switch

Run from any machine. `$T` is a member's access token, `$L` a leader's.

```bash
B=https://gabrielafonso.com.br/ipbcb/media
F=gallery/<album-slug>/<a real file>

curl -sI "$B/$F"                                  # 401
curl -sI -H "Authorization: Bearer $T" "$B/$F"    # 200, Content-Type image/*, ETag,
                                                  # Last-Modified, Cache-Control: private, no-cache,
                                                  # X-Content-Type-Options: nosniff, no X-Accel-Redirect
E=$(curl -sI -H "Authorization: Bearer $T" "$B/$F" | awk -F': ' 'tolower($1)=="etag"{print $2}' | tr -d '\r')
curl -sI -H "Authorization: Bearer $T" -H "If-None-Match: $E" "$B/$F"   # 304
curl -sI https://gabrielafonso.com.br/ipbcb/protected-media/$F           # 404 (internal only)
curl -sI --path-as-is -H "Authorization: Bearer $T" "$B/gallery/../../.env"  # 404 (nginx or backend)
```

Also, once: upload a gallery photo whose name has an accent and a space (for example
`Ceia de Natal ção.jpg`) and fetch it as a member — `200` proves the percent-encoded
`X-Accel-Redirect` round-trips (research R-07).

If `ETag`/`304` is missing, or `Cache-Control` appears twice, the fix is in the nginx
location (research R-07), not in the backend.

## 5. App

With the updated app build: open the gallery, close and reopen it — in the nginx access log,
the second pass shows `304`s, not `200`s. Revoke the test account's membership in the admin,
pull to refresh — images stop loading (`403`).
