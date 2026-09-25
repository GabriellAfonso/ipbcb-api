# Contract: Media endpoint

Two consumers: the Android app (sees the public side) and nginx (consumes the internal
redirect). The app-facing URL is unchanged from today; only the requirement to authenticate is
new.

---

## Public side — `GET|HEAD /ipbcb/media/<path>`

### Request

| Part            | Value                                                      |
|-----------------|------------------------------------------------------------|
| `Authorization` | `Bearer <access token>` — required                         |
| `If-None-Match` / `If-Modified-Since` | optional; answered by nginx (production only) |
| Query string    | ignored                                                    |

### Responses

| Status | When | Body | Notable headers |
|--------|------|------|-----------------|
| `200` (production) | allowed, file exists | the file's bytes, streamed by nginx | `Content-Type` (allow-list), `Cache-Control: private, no-cache`, `ETag`, `Last-Modified` (nginx), `X-Content-Type-Options: nosniff` (nginx) |
| `304` (production) | allowed, validator matches | empty | `ETag`, `Cache-Control: private, no-cache` |
| `200` (`DEBUG=True`) | allowed, file exists | the file's bytes, from Django | `Content-Type` (allow-list), `Cache-Control: private, no-cache` |
| `401` | no, expired or malformed token | `{"error_code": "NOT_AUTHENTICATED" \| "AUTHENTICATION_FAILED", "detail": "..."}` | — |
| `403` | authenticated, lacks the folder's audience | `{"error_code": "PERMISSION_DENIED", "detail": "..."}` | — |
| `404` | rejected path, unruled folder, or missing file — indistinguishable | `{"error_code": "NOT_FOUND", "detail": "Arquivo não encontrado: '<path>'"}` | — |
| `405` | any method other than `GET`/`HEAD` (after authentication) | canonical error | — |
| `429` | `media` throttle scope exceeded | `{"error_code": "THROTTLED", "detail": "..."}` | `Retry-After` |

Check order: authentication → path validation → folder rule → audience → file existence.

### Audiences

| First path segment | Readable by |
|--------------------|-------------|
| `gallery`          | members (`Profile.is_member`) |
| `profiles`         | members |
| `members`          | leaders (`Profile.is_admin`) |
| anything else      | nobody (404) |

---

## Internal side — backend → nginx

What the backend returns to nginx for an allowed request in production:

```http
HTTP/1.1 200 OK
Content-Type: image/jpeg
Cache-Control: private, no-cache
X-Accel-Redirect: /ipbcb/protected-media/gallery/retiro-2025/IMG_0042.jpg
Content-Length: 0
```

Guarantees the backend makes to nginx:

- `X-Accel-Redirect` always starts with `/ipbcb/protected-media/`, followed by the validated
  path, percent-encoded (`/` kept). It never contains `..`, `.` or empty segments.
- `Content-Type` is always one of `image/jpeg`, `image/png`, `image/webp`, `image/gif`,
  `application/octet-stream`.
- No `ETag`, `Last-Modified` or `Expires` is set.

What the backend requires from nginx (deploy dependency, `nginx-deploy` repository):

```nginx
# Reached only through X-Accel-Redirect; a direct client request gets 404.
location /ipbcb/protected-media/ {
    internal;
    add_header X-Content-Type-Options "nosniff" always;
    alias /ipbcb/media/;
    # No `expires`, no `add_header Cache-Control`: the backend's private, no-cache must reach
    # the client unchanged. etag stays at its default (on).
}
```

and the removal of the current `location /ipbcb/media/ { alias ...; }` block, so that
`/ipbcb/media/` falls through to the existing `location /ipbcb/` proxy to the backend.
