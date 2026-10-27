# Feature Specification: Bible Videos and Reading Progress

**Feature Branch**: `025-bible-videos`

**Created**: 2026-10-27

**Status**: Draft

**Input**: User description: "Admin and Liderança attach YouTube videos and playlists to Bible
chapters and books; everyone lists them. A signed-in user marks chapters as read and videos as
watched, stored per account and synced from an offline queue." (full request — current state,
decisions and their reasons — in `../TODO/specify_bible_videos_backend.md`; decided in session
`880f5e23-1e97-4c5f-baed-23d3ecd24b2b` of the app project, 2026-10-27.)

## Context

The Bible (`specs/bible/spec.md`) is served from two static translations (NAA, ARA) with no
database model. This feature adds two things on top of it:

1. **Bible videos** — YouTube videos and playlists that leadership links to chapters and/or whole
   books, listed for everyone in the reader. The server reads the title and thumbnail from YouTube
   once, when the link is saved, so the app never asks YouTube for metadata.
2. **Reading progress** — chapters a signed-in user has read and videos they have watched, kept on
   the server per account so the state survives reinstall and follows the user across devices.
   The app sends changes from an offline queue; the server keeps whichever change was made last.

### Relation to other specs

- **`specs/bible/spec.md`** — the domain spec; gains videos, places, progress and their endpoints.
  The translations and their endpoints are unchanged.
- **`specs/012-feature-role-permissions/`** — gains the scope `bible_videos`.
- **`specs/001-api-error-handling/`** — every error follows its `{"error_code", "detail"}` format.
- **`specs/006-hymnal-view-history/`** — same batch-sync contract shape (`accepted`/`rejected`
  per item; the app drops every item of a chunk the server answered).

## Definitions

### Book identifier

The book's `abbrev` exactly as the Bible endpoints serve it (`Gn`, `Êx`, `Jó`, `1Tn`, ... — 66
books, canonical order). Both translations share the same books and chapter counts, so videos and
progress do not depend on the translation. On input the server matches the identifier ignoring
case and always stores and returns the canonical spelling.

> The saved request described identifiers as lowercase ASCII (`gn`, `ex`). The served data uses
> mixed case and accents (`Gn`, `Êx`), and the app already navigates by the served value, so the
> served value is the identifier. Case-insensitive input keeps a lowercase client working.

### Place

Where a video appears: a book and either one chapter of it or the whole book (`chapter` null).
Chapters are 1-based. A range is not a concept: "Gn 1–3" is three places, each with its own order;
ranges that cross books come for free.

### Video kind

`video` (one YouTube video) or `playlist` (a YouTube playlist).

### Change time (`changed_at`)

The moment, on the user's device, a progress change was made. It decides which of two conflicting
changes wins — not the order in which they reach the server.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Leadership links a video to chapters (Priority: P1)

A pastor pastes a YouTube link and picks Gênesis 1, 2 and 3. The server reads the title and
thumbnail from YouTube and the video appears at the end of each of those chapters' lists.

**Why this priority**: without videos there is nothing to list or watch; this is the core of the
first capability.

**Independent Test**: with a fake YouTube lookup, a Liderança user posts a valid link with three
places; expect 201 with the title and thumbnail from the lookup and three places, each with the
next free position.

**Acceptance Scenarios**:

1. **Given** a Liderança user and a valid public video link, **When** they save it with places
   Gn 1 and Gn (whole book), **Then** the video is created with title and thumbnail from YouTube,
   and each place gets the position after the last video already in that place.
2. **Given** a link to a video already saved, **When** anyone saves it again, **Then** no second
   video is created; the answer is 409 `BIBLE_VIDEO_EXISTS` and carries the existing video, so the
   app can open its places screen.
3. **Given** a link that is not a YouTube video or playlist, **When** it is saved, **Then** the
   answer is 400 `BIBLE_VIDEO_INVALID_URL`.
4. **Given** a private, removed or non-embeddable video, **When** it is saved, **Then** the answer
   is 400 `BIBLE_VIDEO_UNAVAILABLE` and nothing is stored.
5. **Given** YouTube does not answer in time or fails, **When** a link is saved, **Then** the answer
   is 503 `BIBLE_VIDEO_LOOKUP_FAILED` and nothing is stored.
6. **Given** a Mídia user or a member with no role, **When** they save a link, **Then** the answer
   is 403 `PERMISSION_DENIED`.
7. **Given** a place naming an unknown book or a chapter beyond the book's chapter count, **When**
   it is saved, **Then** the answer is 400 and nothing is stored.

---

### User Story 2 - Anyone lists the videos (Priority: P1)

The reader opens Gênesis 1; the app already holds every video and its places from one cached
response and shows the videos of Gn 1 and of Gênesis as a whole, in their manual order.

**Why this priority**: listing is what makes the videos reach the church.

**Independent Test**: seed two videos with places; request the list without a token; expect both
with their places; repeat with the returned ETag and expect 304.

**Acceptance Scenarios**:

1. **Given** saved videos, **When** anyone (signed in or not) lists them, **Then** they get every
   video with id, kind, YouTube id, URL, title, thumbnail and its places (book, chapter, position).
2. **Given** a list already fetched, **When** it is fetched again with the same ETag and nothing
   changed, **Then** the answer is 304 with no body.
3. **Given** a video was added, reordered or removed since, **When** it is fetched with the old
   ETag, **Then** the answer is 200 with the new list.

---

### User Story 3 - Leadership edits where a video appears and its order (Priority: P2)

A leader opens "Locais do vídeo", adds Êxodo 1 and removes Gn 3; on another screen they drag the
videos of Gn 1 into a new order; they also remove a video from one chapter or delete it from all
places.

**Why this priority**: keeps the lists right over time; the first save already gives a usable
list.

**Independent Test**: create a video in Gn 1, Gn 2; replace its places with Gn 2, Êx 1; expect
Gn 2 kept with its position, Gn 1 gone, Êx 1 appended; reorder Êx 1 and expect positions 0..n-1.

**Acceptance Scenarios**:

1. **Given** a video in Gn 1 and Gn 2, **When** its places are replaced with Gn 2 and Êx 1,
   **Then** Gn 2 keeps its position, Gn 1 is removed and Êx 1 is appended to the end of Êx 1.
2. **Given** a video, **When** its places are replaced with an empty list, **Then** the video is
   deleted.
3. **Given** a video in Gn 1 and Gn 2, **When** the Gn 1 place is removed, **Then** only Gn 2
   remains; **When** Gn 2 is then removed, **Then** the video is deleted.
4. **Given** a video, **When** it is deleted, **Then** it disappears from every place, and every
   user's watched mark for it is gone.
5. **Given** the videos 7, 42, 3 of Gn 1, **When** the order is set to [3, 7, 42], **Then** those
   get positions 0, 1, 2 in Gn 1 and the order of Gn 2 is untouched.
6. **Given** the videos 7, 42 of Gn 1, **When** an order is sent missing one, adding another or
   repeating one, **Then** the answer is 400 `BIBLE_VIDEO_ORDER_MISMATCH` and nothing changes.
7. **Given** a Mídia user, **When** they try any of these, **Then** the answer is 403.

---

### User Story 4 - A member marks chapters read and videos watched (Priority: P2)

A member marks Gn 1 as read on their phone, offline. Later, online, the app sends its queued
changes; on their tablet the mark appears after the tablet fetches the state.

**Why this priority**: the second capability; independent from the video management.

**Independent Test**: sign in, send a batch with chapter and video changes, fetch the state; expect
only `done` items; send an older change for the same chapter and expect no effect.

**Acceptance Scenarios**:

1. **Given** a signed-in user, **When** they send `{"type": "chapter", "book": "Gn", "chapter": 1,
   "done": true, ...}`, **Then** the item is accepted and Gn 1 appears in their state.
2. **Given** Gn 1 unmarked at 10:05 on device A, **When** device B later sends a mark made at 10:00,
   **Then** the item is accepted but ignored and Gn 1 stays unmarked.
3. **Given** a batch with one unknown book, one chapter out of range, one unknown video and one
   change time far in the future, **When** it is sent, **Then** each of those comes back in
   `rejected` with its reason and the valid items are applied.
4. **Given** a batch over the size limit or with an unknown field, **When** it is sent, **Then** the
   answer is 400 and nothing is applied.
5. **Given** no token, **When** progress is read or sent, **Then** the answer is 401.
6. **Given** two users, **When** each reads their state, **Then** each sees only their own marks.
7. **Given** a user whose account is deleted, **Then** all their progress is deleted with it.

---

### Edge Cases

- **Same video in one place twice**: refused — a place lists each video once (400 on create or
  replace with repeated places).
- **Playlist link that also names a video** (`watch?v=X&list=Y`): treated as the video X.
- **Start time in the link** (`t=90`): kept in the stored URL; the identity is still the video id,
  so the same video with another start time is the same video (409).
- **Saving a video whose places are all invalid or empty**: refused — at least one valid place.
- **Video renamed on YouTube later**: keeps the title read when saved.
- **Video deleted while a device holds a queued "watched" for it**: that item is rejected as
  `unknown_video`; the app drops it.
- **Unmarking something never marked**: stored as an unmarked row (it still guards against an
  older mark arriving later).
- **Same change time on two devices**: the one already stored wins (the newer must be strictly
  later).
- **Removing a place that is not linked to the video**: 404 `BIBLE_PLACE_NOT_FOUND`.
- **Two leaders appending to the same place at once**: positions may tie; the list orders ties by
  video id, and the next reorder fixes it.

## Requirements *(mandatory)*

### Functional Requirements

**Access**

- **FR-001**: A new panel scope `bible_videos` MUST exist. Admin holds `owner` on it in code;
  Liderança MUST receive `owner` through a data migration whose reverse removes it; Mídia gets
  nothing. Writes use the method defaults (POST/PUT manage, DELETE owner).
- **FR-002**: Listing videos MUST be public (no sign-in), like the Bible text.
- **FR-003**: Progress endpoints MUST require a signed-in user and no scope; each user reads and
  writes only their own progress.

**Videos**

- **FR-004**: A video MUST be identified by its kind and YouTube id; there MUST be at most one
  video per (kind, YouTube id).
- **FR-005**: Saving a link MUST accept `youtube.com/watch?v=`, `youtu.be/`, `youtube.com/shorts/`,
  `youtube.com/live/` (also on `m.youtube.com`, `music.youtube.com` and `www.` hosts) as videos,
  and `youtube.com/playlist?list=` as playlists. Anything else MUST be refused with
  `BIBLE_VIDEO_INVALID_URL`.
- **FR-006**: The stored URL MUST be the canonical one the server builds
  (`https://www.youtube.com/watch?v=<id>`, plus `&t=<seconds>` when the link had a start time;
  `https://www.youtube.com/playlist?list=<id>` for playlists).
- **FR-007**: On save, the server MUST read title and thumbnail from YouTube once. For videos the
  thumbnail is `https://i.ytimg.com/vi/<id>/hqdefault.jpg`; for playlists, YouTube's own. A
  private, removed or non-embeddable target MUST be refused with `BIBLE_VIDEO_UNAVAILABLE`; a
  timeout or YouTube failure with 503 `BIBLE_VIDEO_LOOKUP_FAILED`. Metadata is never refreshed
  afterwards and the title cannot be edited.
- **FR-008**: The duplicate check MUST happen before the YouTube lookup, and a duplicate MUST be
  answered with 409 `BIBLE_VIDEO_EXISTS` carrying the existing video.
- **FR-009**: A new place MUST be appended to the end of its place's list (position = last + 1,
  starting at 0).
- **FR-010**: Replacing a video's places MUST keep the position of places that stay, append new
  ones, delete removed ones, and delete the video when the list is empty.
- **FR-011**: Removing one place MUST delete the video when it was the last place.
- **FR-012**: Deleting a video MUST remove it from every place and remove every user's progress on
  it.
- **FR-013**: Setting the order of one place MUST receive exactly the videos of that place, each
  once, and set their positions to 0..n-1 in the given order, touching no other place.
- **FR-014**: Every book identifier MUST name one of the 66 books, matched ignoring case and stored
  canonically; every chapter MUST be between 1 and the book's chapter count. Otherwise the request
  MUST be refused with `BIBLE_PLACE_INVALID`.
- **FR-015**: The list MUST return every video with its places, places ordered by book (canonical
  order), whole book first, then chapter, and videos within a place by position; it MUST support
  ETag / `If-None-Match` with 304.

**Progress**

- **FR-016**: The server MUST keep, per user, one row per chapter and one row per video touched,
  each with a done flag and the change time. Unmarked rows MUST be kept (tombstones).
- **FR-017**: Reading the state MUST return only done items: chapters grouped by book (canonical
  identifiers, chapters ascending) and watched video ids.
- **FR-018**: A sync batch MUST apply each change only when there is no row for its target or its
  change time is strictly later than the stored one; older changes are accepted and ignored.
- **FR-019**: A change time MUST carry a UTC offset; one more than 5 minutes ahead of the server
  clock MUST be rejected for that item.
- **FR-020**: An unknown book, a chapter out of range, an unknown video, a missing offset or a time
  too far ahead MUST reject only that item, with a reason; the rest of the batch is applied.
- **FR-021**: The answer MUST be 200 with `accepted` (indexes) and `rejected` (`index`, `reason`),
  covering every item of the batch.
- **FR-022**: A batch over 500 items, empty, or with any unknown or missing field or wrong type
  MUST be refused whole with 400 `VALIDATION_ERROR`.
- **FR-023**: When several items in one batch target the same chapter or video, they MUST be
  resolved by the same rule as if sent one by one in order.
- **FR-024**: Deleting a user MUST delete their progress.

### Contract

`GET api/bible/videos/` (public, ETag):

```json
[{"id": 42, "kind": "video", "youtube_id": "dQw4w9WgXcQ",
  "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "title": "...",
  "thumbnail_url": "https://i.ytimg.com/vi/dQw4w9WgXcQ/hqdefault.jpg",
  "places": [{"book": "Gn", "chapter": null, "position": 3}, {"book": "Gn", "chapter": 1, "position": 0}]}]
```

| Method and path | Access | Body | Success |
|---|---|---|---|
| `POST api/bible/videos/` | `bible_videos` manage | `{"url", "places": [{"book", "chapter"}]}` (≥ 1 place) | 201 video |
| `PUT api/bible/videos/<id>/places/` | manage | `{"places": [{"book", "chapter"}]}` | 200 video; 204 when the list was empty (video deleted) |
| `DELETE api/bible/videos/<id>/places/?book=Gn&chapter=1` | owner | — (`chapter` absent = whole book) | 200 video; 204 when it was the last place |
| `DELETE api/bible/videos/<id>/` | owner | — | 204 |
| `PUT api/bible/videos/order/` | manage | `{"book", "chapter", "video_ids": [...]}` (`chapter` null = book) | 204 |
| `GET api/bible/progress/` | signed in | — | 200 `{"chapters": {"Gn": [1, 2]}, "videos": [42]}` |
| `POST api/bible/progress/sync/` | signed in | `{"changes": [...]}` (1–500) | 200 `{"accepted": [0], "rejected": [{"index": 1, "reason": "unknown_video"}]}` |

Sync items: `{"type": "chapter", "book", "chapter", "done", "changed_at"}` or
`{"type": "video", "video_id", "done", "changed_at"}`. Reject reasons: `unknown_book`,
`unknown_chapter`, `unknown_video`, `changed_at_without_offset`, `changed_at_in_future`.

Errors (`{"error_code", "detail"}`, pt-BR):

| Code | Status | When |
|---|---|---|
| `BIBLE_VIDEO_INVALID_URL` | 400 | Link not a supported YouTube video/playlist |
| `BIBLE_VIDEO_UNAVAILABLE` | 400 | YouTube says private/removed/not embeddable |
| `BIBLE_VIDEO_LOOKUP_FAILED` | 503 | YouTube timeout or failure |
| `BIBLE_VIDEO_EXISTS` | 409 | Same kind and YouTube id already saved; body adds `"video": {...}` |
| `BIBLE_PLACE_INVALID` | 400 | Unknown book, chapter out of range, repeated place, no place on create |
| `BIBLE_VIDEO_ORDER_MISMATCH` | 400 | Order list is not exactly the place's videos |
| `BIBLE_VIDEO_NOT_FOUND` | 404 | Unknown video id |
| `BIBLE_PLACE_NOT_FOUND` | 404 | Removing a place the video is not in |
| `VALIDATION_ERROR` | 400 | Malformed body, unknown field, batch size |
| `PERMISSION_DENIED` | 403 | Missing scope level |

### Key Entities

- **Bible video**: kind, YouTube id (unique together), canonical URL, title, thumbnail URL, who
  created it (kept null if that user is deleted), created/updated times.
- **Video place**: video, book, chapter (null = whole book), position. Unique per (video, book,
  chapter), including the whole-book case.
- **Chapter progress**: user, book, chapter, done, change time. Unique per (user, book, chapter).
- **Video progress**: user, video, done, change time. Unique per (user, video). Deleted with the
  video or the user.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A leader can link a public video to several chapters in a single save, and it shows
  in each chapter's list on the next list fetch.
- **SC-002**: The app never needs to call YouTube to show a video's title or thumbnail.
- **SC-003**: A marked chapter appears on a second device of the same account after one state
  fetch, and an offline change made earlier than a later unmark never brings the mark back.
- **SC-004**: A batch covering a whole book (150 chapters of Salmos) is accepted in one request.
- **SC-005**: Re-fetching an unchanged video list costs no body (304).

## Assumptions

- The video list stays small (a few hundred videos), so one unpaginated public response is fine.
- YouTube's oEmbed endpoint needs no API key and is reachable from the server.
- Device clocks are roughly right; the 5-minute future tolerance only guards against broken
  clocks, not against skew between devices.
- Progress volume (at most 1,189 chapters plus videos per user) needs no purge.

## Out of Scope

- Reading plans, overall Bible percentage, streaks, statistics, reports on progress.
- Progress for signed-out users.
- Editing a video title, refreshing metadata, an admin listing beyond the public list.
- Push notifications about new videos.
