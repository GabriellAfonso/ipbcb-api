# Research: Protected Media Access

Every decision below was checked against the code on branch `009-protected-media-access`
(forked from `dev` at `ff91410`) and against `nginx-deploy/nginx/conf.d/default.conf`.

---

## R-01 — Path-addressed route instead of object-id routes

**Decision**: Keep the public URL `/ipbcb/media/<path>` and decide access from the path, as
the spec requires.

**Rationale**: An earlier draft of this work (`../TODO/specify_protected_media.md`, outside
the repository, 2026-09-01) proposed object-id routes (`/api/gallery/photos/{id}/file/`) and
called any path-based route "a path traversal that hands out any file nginx can reach". That
risk is real for a naive implementation, and it is closed here by three independent layers
rather than by changing the URL:

1. **Segment validation in the service** (R-04): no `..`, `.`, empty segment, backslash,
   control character or leftover `%` ever reaches the filesystem or the redirect.
2. **Containment on the resolved file** (R-05): the repository resolves symlinks and refuses
   anything whose real path is outside `MEDIA_ROOT`.
3. **nginx itself**: the redirect target is an `internal` location whose `alias` is the media
   directory, so even a validation bug can only reach files *inside* the media directory —
   never `.env` or source. nginx also runs its own unsafe-URI check on `X-Accel-Redirect`
   values and refuses `..` segments.

What path-addressing buys: no serializer, API or app URL change (`photo_url` and `image` keep
their values), and one rule table that also covers files no model points to yet (the members
feature). The earlier draft also required 404 instead of 403 so a denial does not confirm
existence; the check order in R-03 gets the same property, since a caller without the folder's
permission gets 403 before existence is ever looked at.

**Alternatives considered**: object-id routes — rejected by the spec's decided behaviour; each
new media-bearing model would need its own route, and every client URL would change.

---

## R-02 — Where the feature lives

**Decision**: A new package `server/features/media/` (views, services, repositories, dtos,
tests, urls). It is **not** added to `INSTALLED_APPS`: it has no models, admin or migrations.
Its URLs are mounted from `config/urls.py` like every other feature.

**Rationale**: The rule table spans three features' folders (`gallery`, `profiles`,
`members`). Putting it in any one of them would make that feature own the others' access
rules. The constitution forbids features importing each other; `features/media` imports
nothing from them — folder names are string literals, and the permissions it needs already
live in `core.http.permissions`. `core/` is reserved for entities shared by two or more
features, which this is not.

**Alternatives considered**: `core/http/media.py` — rejected, `core` would gain a view and a
service that no second feature uses.

---

## R-03 — One service call decides everything, in spec order

**Decision**: `MediaAccessService.authorize(requested_path, viewer) -> MediaFile`. Inside, in
order: validate the path (R-04) → pick the folder rule → check the viewer against it → locate
the file (R-05). Each step raises a domain exception; the last returns the file. Authentication
happens before, in DRF (`IsAuthenticated`).

The view builds `viewer` as a `MediaViewer(is_member, is_leader)` DTO by calling the existing
permission classes — `IsMemberUser().has_permission(request, self)` and
`IsAdminUser().has_permission(request, self)` — so the flags are read exactly the way every
other endpoint reads them (FR-008), and the service never touches `request`.

**Rationale**: The spec's check order (auth → path → rule → permission → existence) is what
stops a plain member from learning whether a `members/` file exists. Keeping all four
post-auth steps in one method makes that order a property of one function a unit test can pin,
and gives one place to write the single decision log line (R-09). Splitting the permission
check into the view would split the log into two call sites.

**Found while researching — must be fixed for the spec's "no profile row → 403, never 500"
edge case**: both permission classes evaluate `request.user.profile` *before* `getattr`
applies its default — `getattr(request.user.profile, "is_member", False)`. For a user with no
`Profile` row the attribute access itself raises `RelatedObjectDoesNotExist`, which escapes
as a 500 on every `IsMemberUser`/`IsAdminUser` view today. That exception subclasses
`AttributeError` (Django's reverse one-to-one descriptor), so the fix is to move the access
inside a `getattr` with a default: `getattr(getattr(request.user, "profile", None),
"is_member", False)`. Regression test in `features/accounts/tests/unit/test_permissions.py`.

**Alternatives considered**: `resolve()` in the service, permission in the view, `locate()` in
the service — rejected for the split logging and because the order would then be enforced by
the view's statement order rather than by the service.

---

## R-04 — Path validation, never normalization

**Decision**: The path the view receives (already percent-decoded once by the ASGI server) is
split on `/` and rejected if:

- it is empty, or starts with `/` (absolute);
- any segment is empty (`a//b`, trailing `/`), `.` or `..`;
- it contains `\`, `\x00`, or any character below `0x20` or equal to `0x7f`;
- it contains `%` — a second encoding layer (`%252e` arrives as `%2e`). Safe to forbid:
  Django's `get_valid_filename` strips `%` from every upload name, and profile photos are
  `<uuid hex>.<ext>`, so no stored file has one;
- it has fewer than two segments (a folder and a file).

Nothing is collapsed or rewritten. The path that passes is used verbatim for rule selection and
for the redirect. `gallery/../members/x.jpg` is rejected (404), not re-judged as `members/`.

**Rationale**: Normalization (`posixpath.normpath`, `Path.resolve`) turns validation into
"compute what the attacker meant, then judge it", which is where traversal bugs live.
Rejecting every suspicious segment means the checked string and the served string are the same
string. Decided with the user during planning (spec FR-003/FR-004, US5.2 amended).

**Alternatives considered**: normalize then check containment — rejected as above.

---

## R-05 — Filesystem access behind a repository

**Decision**: A `MediaFileRepository` Protocol with `locate(relative_path) -> Path | None`
and `open(path) -> BinaryIO`. The implementation `FileSystemMediaRepository(root)`:

- resolves `root` and `root / relative_path` with `Path.resolve(strict=True)` (follows
  symlinks, raises on missing);
- returns `None` when the file is missing, when the resolved path is not
  `is_relative_to(resolved_root)`, or when it is not a regular file.

`root` is injected from `settings.MEDIA_ROOT` through a `providers.Callable` in `config/di.py`,
evaluated on every provision, so `override_settings(MEDIA_ROOT=tmp_path)` works in tests.

**Rationale**: CLAUDE.md makes repositories the persistence layer and requires external I/O to
be faked in service tests. The service then stays pure string logic plus one repository call,
testable with a named `FakeMediaFileRepository`.

A symlink escaping `MEDIA_ROOT` returns `None` — the service cannot tell it from a missing
file, and reports it as not found. That is intended: the caller learns nothing either way.

---

## R-06 — Route pattern derived from `MEDIA_URL`

**Decision**: Mount the view with
`re_path(rf"^{media_route_prefix()}(?P<requested_path>.*)$", ...)`, where the prefix is
`MEDIA_URL` with `FORCE_SCRIPT_NAME` removed and the leading `/` stripped.

| Settings | `MEDIA_URL` | `FORCE_SCRIPT_NAME` | Route prefix |
|----------|-------------|---------------------|--------------|
| prod     | `/ipbcb/media/` | `/ipbcb` | `media/` |
| dev/test | `/ipbcb/media/` | unset    | `ipbcb/media/` |

**Rationale**: Under ASGI, Django strips `FORCE_SCRIPT_NAME` from `path_info` in production,
so the API routes are `api/...` there. In dev there is no script name, yet the serializers
still emit `/ipbcb/media/...` (that is exactly how the removed `static()` helper worked). A
single hardcoded pattern would be wrong in one of the two. `.*` (not `.+`) sends even
`/ipbcb/media/` through the view, so it gets a 401/404 in the canonical shape instead of
Django's HTML 404.

---

## R-07 — Response shape per delivery mode

**Decision**:

| | Production (`DEBUG=False`) | Development (`DEBUG=True`) |
|---|---|---|
| Class | `HttpResponse(b"", status=200)` | `FileResponse(service.open(media_file))` |
| `X-Accel-Redirect` | `quote(PROTECTED_MEDIA_LOCATION + path, safe="/")` | absent |
| `Content-Type` | from R-08 | from R-08 |
| `Cache-Control` | `private, no-cache` | `private, no-cache` |
| `ETag` / `Last-Modified` | **not set** (nginx supplies them) | not set |

`PROTECTED_MEDIA_LOCATION = "/ipbcb/protected-media/"` lives in `config/settings/base.py`
beside `MEDIA_URL`. It is an nginx-internal URI, not a client URL.

**Rationale**:
- **Percent-encoding the redirect**: gallery filenames keep their original Unicode letters
  (`get_valid_filename` keeps `\w`, which includes `ç`, `ã`). Django MIME-encodes a non-Latin-1
  header value (`=?utf-8?b?...?=`), which nginx would take literally. nginx unescapes an
  `X-Accel-Redirect` URI that contains `%`, so the encoded form reaches the right file.
- **Which upstream headers survive the redirect**: nginx copies `Content-Type`,
  `Cache-Control`, `Expires`, `Set-Cookie`, `Content-Disposition` and `Accept-Ranges` from the
  upstream response into the internal redirect; it does not copy `ETag`, `Last-Modified`,
  `Vary` or `Content-Length`. So our `Cache-Control` reaches the client, and the static
  module's own `ETag`/`Last-Modified` plus its `304` handling of `If-None-Match` /
  `If-Modified-Since` apply to the real file. The `Vary: Accept` DRF adds does not reach the
  client either, which matches FR-013 (no `Vary: Authorization`). **To confirm on the server**
  after the nginx switch (quickstart §4); if a header behaves differently, the fix belongs in
  the nginx location, not here.
- **No `ConditionalGetMiddleware`** in `MIDDLEWARE`, so nothing in Django computes an ETag
  for the empty body. A test pins that the redirect response carries no validator.
- **HEAD** is served by Django's automatic `head = get`; nginx answers it without a body.

---

## R-08 — `Content-Type` from an allow-list, never nginx's guess

**Decision**: The service maps the file's lowercased extension through a fixed table —
`jpg`/`jpeg` → `image/jpeg`, `png` → `image/png`, `webp` → `image/webp`, `gif` → `image/gif`
— and anything else to `application/octet-stream`. The view sets it explicitly in both modes.

**Rationale**: nginx keeps an upstream `Content-Type` and only falls back to `mime.types` when
it is empty. Leaving Django's default `text/html; charset=utf-8` would label every image as
HTML. Deleting the header would let `mime.types` guess from the extension — and that guess is
unsafe for gallery files: `GalleryService.upload_photos` validates the decoded content but
`GalleryRepositoryImpl.create_photo` stores the **original** filename, so an image/HTML polyglot
uploaded as `x.html` would be served as `text/html` on the application's origin. The
allow-list makes that impossible regardless of what is on disk; `octet-stream` plus the
`nosniff` header on the internal location means no browser renders it.

**Found while researching (out of scope, reported to the user)**: the gallery upload keeping
the original extension contradicts the constitution's "stored extension is derived from the
detected format" rule.

---

## R-09 — Decision log

**Decision**: One `logger.info("media_access", extra={"folder": ..., "outcome": ...})` per
authorized request, from the service. `outcome` ∈ `allowed`, `forbidden`, `not_found`,
`rejected`, `unruled`. `folder` is the first segment **only when it is a ruled folder**
(`gallery`, `profiles`, `members`), otherwise `null` — the first segment of a rejected or
unruled path is attacker-controlled text and is not logged.

**Rationale**: FR-019. Existing structured-log style (`hymnal_history_ingest`). The request
log keeps full paths (spec clarification Q3); only this line is restricted.

---

## R-10 — Domain exceptions and the 403 mapping

**Decision**: In `core/domain/exceptions.py`:

- new generic `PermissionDeniedError(DomainError)`, `error_code = "PERMISSION_DENIED"`, mapped
  to `403` in `core/http/exceptions.py::_DOMAIN_STATUS_MAP` — the same code DRF's
  `PermissionDenied` already produces;
- `MediaAccessDeniedError(PermissionDeniedError)`;
- `MediaPathRejectedError`, `MediaFolderNotRuledError`, `MediaFileNotFoundError`, all
  `(NotFoundError)`.

The three not-found classes share one user-facing message (`"Arquivo não encontrado: '<path>'"`
with the requested path), so the response cannot tell rejection, unruled folder and missing
file apart. The distinction exists for the decision log and for tests.

**Rationale**: Domain errors, not `Http404`/DRF errors, from services (CLAUDE.md §2). There is
no 403 domain base today; the members feature will need one too.

---

## R-11 — Throttling

**Decision**: `throttle_classes = [ScopedRateThrottle]`, `throttle_scope = "media"`, rate
`"media": "3000/hour"` in `base.py`, and `"media": "99999/min"` in `test.py` (explicit
`throttle_classes` keep throttling even when the test settings empty the defaults — same
situation as `hymnal_ingest`).

**Rationale**: Spec FR-017. Declaring `throttle_classes` replaces the defaults, so the `user`
quota is untouched by image loads. DRF checks permissions before throttles, so anonymous
requests get their 401 without touching the counter.

**Known limitation (pre-existing, not changed)**: no `CACHES` backend is configured, so every
DRF throttle counter lives in per-worker `LocMemCache`; with 4 gunicorn workers the effective
ceiling is up to 4× the configured rate. This applies to every scope already.

---

## R-12 — Tests under `DEBUG=True`

**Decision**: `config/settings/test.py` sets `DEBUG = True`, so tests of the production path
use `@override_settings(DEBUG=False)`; the view reads `settings.DEBUG` per request, so the
override applies. Media fixtures are written to `tmp_path` with
`override_settings(MEDIA_ROOT=tmp_path)`. The symlink test is skipped when the OS refuses to
create one (Windows without developer mode).
