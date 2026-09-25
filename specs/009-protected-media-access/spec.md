# Feature Specification: Protected Media Access

**Feature Branch**: `009-protected-media-access`

**Created**: 2026-09-25

**Status**: Draft

**Input**: User description: "Protect user-uploaded media behind authentication. Every media
file is served only to authenticated users allowed to see it, while nginx still streams the
bytes." (full request, including the decided behaviour and required tests, in the
`/speckit-specify` invocation that created this directory)

## Overview

Every file under `MEDIA_ROOT` is public today. nginx serves `location /ipbcb/media/` with an
`alias` straight from disk, so no request for a media file ever reaches Django and no
permission is checked. The API endpoints that *list* gallery photos require `IsMemberUser`, but
the image URLs they return can be fetched by anyone who holds them, logged in or not.

Holding them is easy. Gallery files are stored as `gallery/{slugify(album.name)}/{original
filename}`, so a camera-style name such as `IMG_0042.jpg` under a known album is a guess, not a
secret. Profile photos were moved to random filenames as a stop-gap
(`ProfileRepositoryImpl.save_photo`), whose own comment names authenticated delivery as the
real fix.

The upcoming members feature will store photos that only church leaders may see. That feature
must not ship onto a media location with no access control, so this one closes the gap first.

**The contract:** the public URL of every media file stays `/ipbcb/media/<path>`. A request for
it reaches the backend, which decides — by who is asking and by the path's top-level folder —
whether to allow it. When allowed, the backend tells nginx which file to stream and nginx sends
the bytes; the backend never streams file content in production. No API response changes: the
`photo_url` of a profile and the `image` of a gallery photo keep their current values.

**Scope**: backend only. Two coordinated changes live outside this repository and are listed
under *Dependencies* as deploy prerequisites, not as requirements of this spec: the nginx
location switch and the Android app sending its token with image requests.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A leaked media URL is useless without an account (Priority: P1)

Someone who is not logged in — a former visitor with an old link, a scraper, a person who
guessed `gallery/retiro-2025/IMG_0042.jpg` — requests a media file directly.

**Why this priority**: This is the hole. Everything else in this feature refines who, among
logged-in users, sees what; this story alone is what makes media stop being public.

**Independent Test**: Place a file under `gallery/`, request its media URL without
credentials, and confirm nothing about the file is returned.

**Acceptance Scenarios**:

1. **Given** a file exists at `gallery/retiro-2025/IMG_0042.jpg`, **When** a request with no
   credentials asks for `/ipbcb/media/gallery/retiro-2025/IMG_0042.jpg`, **Then** the response
   is `401` in the canonical error shape and carries no file content and no redirect to it.
2. **Given** the same file, **When** the request carries an expired or malformed token,
   **Then** the response is `401`.
3. **Given** no credentials, **When** the request asks for a path that does not exist, **Then**
   the response is also `401` — an anonymous caller cannot tell existing files from missing
   ones.

---

### User Story 2 - Members keep seeing gallery and profile photos in the app (Priority: P1)

A logged-in member opens the gallery or a list showing other members' profile photos. Images
load exactly as before.

**Why this priority**: Closing the hole must not break the app. A protection that leaves the
gallery blank for the congregation would be rolled back the same day.

**Independent Test**: Log in as a member, request a gallery file and a profile photo through
their public media URLs, and confirm the backend instructs nginx to serve each one, with a
cache policy that lets the phone keep the image on disk, revalidating it on every use, but forbids
shared caches.

**Acceptance Scenarios**:

1. **Given** a logged-in member and an existing file `gallery/retiro-2025/IMG_0042.jpg`,
   **When** the member requests `/ipbcb/media/gallery/retiro-2025/IMG_0042.jpg`, **Then** the
   response is `200` with an empty body, an internal redirect header pointing to
   `/ipbcb/protected-media/gallery/retiro-2025/IMG_0042.jpg`, and `Cache-Control: private, no-cache`
   with no `Vary: Authorization` and no validators of its own.
2. **Given** a logged-in member and an existing profile photo of *another* member at
   `profiles/ana.paula/6f1c2d….png`, **When** the member requests it, **Then** the outcome is
   the same as scenario 1 — any member may see any profile photo.
3. **Given** a logged-in user whose profile is **not** a member, **When** they request either
   file, **Then** the response is `403`.
4. **Given** a logged-in member, **When** they request `gallery/retiro-2025/missing.jpg`, which
   does not exist, **Then** the response is `404`.

---

### User Story 3 - Leader-only photos are reserved before they exist (Priority: P2)

The upcoming members feature will store photos under `members/`. Only church leaders
(`Profile.is_admin`) may see them. The rule is in place before any file is written there.

**Why this priority**: No file lives under `members/` yet, so nothing leaks today without it.
It is part of this feature because the members feature must find the rule already enforced,
not have to remember to add it.

**Independent Test**: Place a file under `members/`, request it as a plain member and as a
leader, and compare.

**Acceptance Scenarios**:

1. **Given** an existing file under `members/`, **When** a logged-in member who is not a leader
   requests it, **Then** the response is `403`.
2. **Given** the same file, **When** a logged-in leader requests it, **Then** the response is
   `200` with the internal redirect to `/ipbcb/protected-media/members/…`.
3. **Given** a logged-in user who is a leader but not flagged as a member, **When** they
   request a file under `members/`, **Then** it is allowed — the leader rule does not also
   require membership. *(See Assumptions.)*

---

### User Story 4 - Files outside any known folder are not served to anyone (Priority: P2)

A future feature stores files under a new top-level folder, `reports/`, and nobody adds an
access rule for it.

**Why this priority**: Default deny is what keeps this feature correct after it ships. Without
it, every new upload location would be public until someone noticed.

**Independent Test**: Place a file under an unlisted folder and request it as a leader.

**Acceptance Scenarios**:

1. **Given** an existing file at `reports/2026.pdf`, **When** any logged-in user — leader
   included — requests `/ipbcb/media/reports/2026.pdf`, **Then** the response is `404`.
2. **Given** a file placed directly at the root of `MEDIA_ROOT` (`/ipbcb/media/logo.png`),
   **When** any logged-in user requests it, **Then** the response is `404`.

---

### User Story 5 - Path tricks never escape the media folder (Priority: P1)

An authenticated user — possibly a member with a stolen token — crafts a media path meant to
read a file outside `MEDIA_ROOT` (settings, the `.env`, the database dump) or to reach a
leader-only folder through a member-visible prefix.

**Why this priority**: The backend now decides which file nginx streams. A path it gets wrong
is a file-read primitive over the whole server disk, which is worse than the hole being
closed.

**Independent Test**: Send each traversal form as a member and confirm no response ever carries
an internal redirect, and none returns file content.

**Acceptance Scenarios**:

1. **Given** a logged-in member, **When** they request
   `/ipbcb/media/gallery/../../config/settings/base.py`, **Then** the request is rejected and
   no internal redirect is issued.
2. **Given** a logged-in member, **When** they request `/ipbcb/media/gallery/../members/x.jpg`,
   which would stay inside `MEDIA_ROOT`, **Then** it is still rejected (`404`): a `..` segment
   is never collapsed, so it can neither escape the media folder nor move a request from one
   folder's rule to another's.
3. **Given** a logged-in member, **When** the traversal is percent-encoded (`%2e%2e/`,
   `%2e%2e%2f`, `..%2f`) or double-encoded (`%252e%252e`), **Then** it is rejected the same way
   as its plain form.
4. **Given** a logged-in member, **When** the path is absolute (`/ipbcb/media//etc/passwd`) or
   uses a backslash separator (`gallery\..\..\x`), **Then** it is rejected.
5. **Given** a file under `gallery/` that is a symbolic link to a file outside `MEDIA_ROOT`,
   **When** a member requests it, **Then** it is rejected — containment is judged on the file
   the path actually resolves to.

---

### User Story 6 - Local development enforces the same rules (Priority: P3)

A developer runs the backend with `DEBUG=True` and no nginx in front, and the app or a test
client loads images from it.

**Why this priority**: Development without nginx must still work, and must not quietly
re-open public media — otherwise a bug in the rules is only discovered in production.

**Independent Test**: Run with `DEBUG=True`, request a gallery file as a member and as an
anonymous caller.

**Acceptance Scenarios**:

1. **Given** `DEBUG=True` and a logged-in member, **When** they request an existing gallery
   file, **Then** the response is `200` and its body is the file's bytes, with no internal
   redirect header.
2. **Given** `DEBUG=True` and no credentials, **When** the same file is requested, **Then** the
   response is `401` — no development-only route serves media without the checks.

---

### Edge Cases

- **Order of checks.** Authentication, then path validation, then the folder rule, then the
  user's permission, then file existence. A caller without permission for a folder gets `403`
  whether or not the file exists, so existence under `members/` is not observable by a plain
  member.
- **User with no profile row.** Treated as neither member nor leader: `403` on every ruled
  folder. Never a `500`.
- **Folder name without a file** (`/ipbcb/media/gallery`, `/ipbcb/media/gallery/`): `404` for
  every user — the first has no folder segment followed by a file, the second ends in an empty
  segment.
- **Prefix look-alikes**: `gallery-old/x.jpg`, `galleryx.jpg`, `Gallery/x.jpg` do **not** match
  the `gallery/` rule. The rule matches the first path segment exactly, so they fall to default
  deny (`404`).
- **Null byte or control character in the path**: rejected, never passed to the filesystem.
- **Query string** (`?v=2`, a cache-buster the app may add): ignored for rule selection and not
  forwarded into the internal redirect path.
- **HTTP methods**: `GET` and `HEAD` only. Anything else is `405`.
- **Content type**: the file nginx streams must reach the client with the image type of the
  file, not the backend's default HTML content type.
- **Membership revoked after caching**: the phone still has the image on disk, but must
  revalidate before showing it; the revalidation gets `403`, so the image stops being served
  on the next request.
- **Revalidation of an unchanged file**: the request still goes through authentication and the
  rule; when allowed, nginx answers `304` with no body.
- **Revalidation after the file was deleted**: `404`, same as a first request.
- **Orphan files** (a file under an allowed folder whose database record was deleted): still
  served to that folder's audience. Accepted — access is by folder, not by record.

---

## Requirements *(mandatory)*

### Functional Requirements

**Authentication**

- **FR-001**: Every request for `/ipbcb/media/<path>` MUST be answered by the backend's access
  check; no route — production or development — may serve a media file without it. The
  development-only media route in `config/urls.py` MUST be removed.
- **FR-002**: The access check MUST authenticate the caller the same way as every other
  protected endpoint (JWT via the project's standard `IsAuthenticated`). An unauthenticated
  or invalid-token request MUST get `401` in the canonical `{"error_code", "detail"}` shape,
  before the path is examined.

**Path handling**

- **FR-003**: The requested path MUST be decoded exactly once and validated segment by segment
  before any rule is chosen. Validation never rewrites the path — nothing is collapsed or
  stripped — so the path that passes is the one the rule is chosen for and the one sent in the
  internal redirect.
- **FR-004**: A path MUST be rejected when it is absolute, contains an empty, `.` or `..`
  segment (even one that would resolve inside `MEDIA_ROOT`), contains a backslash, a null byte or a control character, still contains a
  percent-encoded sequence after the single decode, or resolves — following symbolic links —
  to a location outside `MEDIA_ROOT`. A rejected path MUST produce `404` and MUST NOT produce
  an internal redirect.

**Access rules**

- **FR-005**: Access MUST be decided by the first segment of the validated path, matched
  exactly:

  | First segment | Who may read         | Source of truth         |
  |---------------|----------------------|-------------------------|
  | `gallery`     | members              | `Profile.is_member`     |
  | `profiles`    | members (any profile)| `Profile.is_member`     |
  | `members`     | church leaders       | `Profile.is_admin`      |
  | anything else | nobody               | —                       |

- **FR-006**: A path whose first segment has no rule, or that has no folder at all, MUST get
  `404` for every user, leaders included (default deny).
- **FR-007**: An authenticated user lacking the permission a rule requires MUST get `403`,
  regardless of whether the file exists.
- **FR-008**: The rules MUST reuse the existing permissions in `core.http.permissions`:
  `IsMemberUser` for members and `IsAdminUser` (which reads `Profile.is_admin`) for church
  leaders. No new permission class — the leader check already exists and is what the members
  feature will reuse for its endpoints.
- **FR-009**: Access MUST NOT depend on any database record linking the file to a gallery
  photo, profile or member. Folder and user are the only inputs.

**Delivery**

- **FR-010**: When the user is allowed and the file exists, the production response MUST be
  `200` with an empty body and the header
  `X-Accel-Redirect: /ipbcb/protected-media/<validated path>`, so nginx streams the file.
- **FR-011**: The internal redirect target MUST always begin with `/ipbcb/protected-media/`
  followed by a path that satisfies FR-004. No input may produce a redirect to any other
  location.
- **FR-012**: When the user is allowed but no regular file exists at the validated path, the
  response MUST be `404`.
- **FR-013**: A successful response MUST carry `Cache-Control: private, no-cache` and no
  `Vary: Authorization`. `private` keeps it out of shared caches; `no-cache` lets the device
  keep the image on disk but forces a revalidation on every use, so each view goes through the
  access check and a revoked membership takes effect on the next request. The validators
  (`ETag`, `Last-Modified`) and the `304` answer to a matching `If-None-Match` /
  `If-Modified-Since` come from nginx serving the redirected file; the backend MUST NOT set
  validators of its own on the redirect response, since they would describe the empty body,
  not the file. An unchanged image is therefore never downloaded twice.
  This departs from the constitution's `private, no-store` + `Vary: Authorization` rule on
  purpose — `no-store` would force a full re-download of every image on every view — and is
  recorded there as a media exception (FR-021).
- **FR-014**: The response MUST let the file reach the client with the content type matching
  its format; the backend's default HTML content type must not be applied to the file.
- **FR-015**: With `DEBUG=True`, the same checks MUST apply in the same order, and a
  successful response MUST carry the file's bytes directly instead of the internal redirect
  header.
- **FR-016**: Only `GET` and `HEAD` are accepted; other methods get `405`.
- **FR-017**: Media requests MUST be throttled under a scope of their own (`media`), separate
  from the default `user` scope, so viewing images never spends the API quota and a `429` on
  images never blocks the API. The scope still caps how fast a stolen token can pull files.
  Revalidations count against it too: with `no-cache` (FR-013), every image shown is one
  request, `304` or not.

**Architecture and observability**

- **FR-018**: The view MUST handle only HTTP concerns. Path validation, containment,
  existence and rule selection MUST live in a service registered in `config/di.py`; rejection
  outcomes MUST be domain exceptions in `core/domain/exceptions.py`, mapped to status codes by
  the existing exception handler.
- **FR-019**: Each access decision MUST be logged through the structured JSON logger with the
  folder (first segment) and the outcome (allowed, forbidden, not found, rejected) only —
  never the rest of the path, file contents, or any member data. This rule governs the
  access-decision log only: the existing request-log middleware keeps recording
  `request.get_full_path()` for media requests like for any other request, so full media paths
  (including `profiles/<username>/…`) do appear there. Accepted — see Assumptions.

**Housekeeping**

- **FR-020**: The comment in `ProfileRepositoryImpl.save_photo`
  (`features/accounts/repositories/profile_repository.py`) that says nginx serves `MEDIA_ROOT`
  straight from disk, and that points to a non-existent `TODO/specify_protected_media.md`,
  MUST be rewritten to describe authenticated delivery and point to this spec. The random
  filename stays, as defence in depth.
- **FR-021**: `specs/constitution.md` MUST record that media is served only through the
  access check, with default deny by folder, and MUST add a media exception to its Caching
  section: media responses use `private, no-cache` with validators from nginx and without
  `Vary: Authorization` (FR-013). The register-oracle entry, which cites
  randomised filenames as what closes the photo-URL leak, MUST also cite the access check.
  The public OpenAPI schema remains an accepted risk, unchanged.
- **FR-022**: `specs/gallery/spec.md` and `specs/accounts/spec.md` MUST state that the image
  and photo URLs they return are readable only by members through the media access check.

### Key Entities

- **Media access rule**: a top-level media folder paired with the audience allowed to read
  files in it (members or church leaders). The set of rules is fixed in code; a folder
  without a rule is unreadable.
- **Media access decision**: the outcome for one request — allowed (with the validated path
  to stream), forbidden, not found, or rejected — plus the folder it was judged under. It is
  what gets logged; the full path is not.
- **Profile** (existing): `is_member` and `is_admin` are the only user attributes the rules
  read.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 0 media files are retrievable without logging in — every file under
  `MEDIA_ROOT` answers `401` to an anonymous request once the deploy sequence is complete.
- **SC-002**: 100% of the traversal forms listed in User Story 5 are rejected, and none of them
  produces an internal redirect or file content.
- **SC-003**: A logged-in member sees the same gallery and profile photos in the app as before
  the change, with no change to any API response.
- **SC-004**: Re-opening an already viewed album on the same phone downloads no image bytes
  again: every unchanged image is answered with `304`.
- **SC-004a**: A user whose membership is revoked can no longer load any gallery or profile
  image from the server on their very next request, cached copies included.
- **SC-005**: A new top-level media folder added by a future feature is unreadable by every
  user until an access rule is written for it.
- **SC-006**: Every test listed in the feature request passes: unauthenticated `401`,
  non-member `403` on `gallery/` and `profiles/`, member `200` with redirect and private
  cache, non-leader `403` and leader allowed on `members/`, unknown folder `404`, traversal
  rejected, missing file `404`, development mode returning the file body.

---

## Assumptions

- **Media throttle rate**: `3000/hour` per user for the `media` scope, three times the API
  rate, because revalidations make every image shown a request. Tunable in settings; the plan
  may revise it with measurements.
- **Full media paths in the request log are accepted.** The request log already records every
  API path; a username inside `profiles/<username>/…` adds nothing the log does not already
  carry elsewhere. The prefix-only rule applies to the new access-decision log.
- **Development mode does not revalidate.** With `DEBUG=True` the backend returns the file
  itself and is not required to answer `304`; conditional behaviour is nginx's, and only
  matters in production.
- **Leader rule does not also require membership.** `is_admin` alone grants `members/`. A
  leader who is not flagged as a member is an account setup mistake, not a reason to hide
  leader-only photos from them. Membership still governs `gallery/` and `profiles/` for
  leaders.
- **Rejected paths answer `404`, not `400`.** A malformed path names no file the caller may
  read; `404` gives an attacker nothing to distinguish probing from a miss.
- **Session authentication** (enabled for the Django admin) is accepted by the check like on
  every other DRF view; the app uses JWT only.
- **No database lookup**: an orphan file under an allowed folder stays readable by that
  folder's audience. Accepted trade-off, decided in the request.
- **Gallery filenames stay as uploaded.** With the access check in place, guessability of
  `gallery/` names no longer exposes anything to non-members; renaming is out of scope.

## Dependencies

Deploy prerequisites outside this repository. They are not requirements of this spec, but
releasing this backend change is only safe in this order, **all on the same day**:

1. **Backend** (this feature). Harmless on its own: nginx still serves `/ipbcb/media/`
   from disk and never reaches the new check.
2. **Android app release**: a single image loader built on the authenticated HTTP client, so
   image requests carry the JWT and use the existing token refresh.
3. **nginx switch** (`nginx-deploy` repository): `location /ipbcb/media/` changes from `alias`
   to proxying to the backend, and a new
   `location /ipbcb/protected-media/ { internal; alias <media dir>/; }` is added, keeping the
   `X-Content-Type-Options: nosniff` header. The `protected-media` location MUST NOT add its
   own `Cache-Control` or `Expires` (no `expires` directive), so the backend's
   `private, no-cache` reaches the client unchanged, and MUST keep nginx's default `ETag` and
   `Last-Modified` on.

Switching nginx before the app update leaves every installed app without images. Like the
metrics block, the nginx part lives outside this project, so the constitution entry
(FR-021) is its only record here.
