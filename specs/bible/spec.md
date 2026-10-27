# Bible Domain

Read-only domain that serves Bible text data. No authentication required — fully public.

## Overview

Provides Bible versions (e.g., ARA, NAA) as structured JSON loaded from static files at startup. The Android app uses this to display Bible text offline-capable after first fetch.

## Data Model

No database models. Data lives in static JSON files under `features/bible/data/`.

### Bible JSON Structure

Each file is named `{VERSION}.json` (e.g., `ARA.json`) and contains a list of books:

```json
[
  {
    "abbrev": "Gn",
    "name": "Gênesis",
    "chapters": [
      ["Verso 1", "Verso 2", "..."],
      ["Verso 1 do cap 2", "..."]
    ],
    "headings": [
      [{"verse": 1, "level": 1, "title": "A criação do Universo"}],
      [
        {"verse": 4, "level": 1, "title": "A formação do homem"},
        {"verse": 18, "level": 1, "title": "A formação da mulher"}
      ]
    ]
  }
]
```

| Field      | Type              | Description                                      |
|------------|-------------------|--------------------------------------------------|
| `abbrev`   | `str`             | Standard abbreviation of the book                |
| `name`     | `str`             | Full name of the book (pt-BR)                    |
| `chapters` | `list[list[Verse]]` | List of chapters, each chapter is a list of verses. `Verse = str \| list[str]` — most verses are plain strings, but some entries (e.g., NAA) contain nested lists for multi-paragraph verses. |
| `headings` | `list[list[Heading]]` | Section headings (pericope titles) of the translation, one list per chapter, parallel to `chapters`. Optional in the file — a version without headings loads with `[]`. |

#### Heading

| Field   | Type  | Description                                                        |
|---------|-------|--------------------------------------------------------------------|
| `verse` | `int` | 1-based verse number the heading is shown **before**               |
| `level` | `int` | Nesting level, `1` (major section) to `3` (sub-subsection). E.g., Mt 5 in ARA: "O sermão do monte" (1) > "Jesus completa o que foi dito aos antigos" (2) > "Do homicídio" (3) |
| `title` | `str` | Heading text exactly as published in the translation               |

Within a chapter, headings are ordered by `verse`, then by `level` — several headings may precede the same verse (e.g., Mt 5:1 has a level 1 and a level 2 heading).

Headings belong to the translation: ARA and NAA have different titles for the same passage. ARA and NAA headings were taken from bibliaonline.com.br.

### Adding a new version

Drop a new `{VERSION}.json` file in `features/bible/data/`. It is loaded automatically at startup.

## Endpoints

### `GET /api/bible/`

Lists available Bible versions.

- **Auth:** none (`AllowAny`)
- **Response `200`:**

```json
{
  "versions": ["ARA", "NAA"]
}
```

Versions are returned sorted alphabetically.

### `GET /api/bible/{name}/`

Returns full Bible data for a specific version.

- **Auth:** none (`AllowAny`)
- **Path params:** `name` — version identifier (case-sensitive, must match filename stem)
- **Response `200`:** the Bible JSON structure (list of books)
- **Response `404`:**

```json
{
  "detail": "Version not found."
}
```

## Business Rules

1. Bible data is **read-only** — no create, update, or delete operations.
2. All versions are loaded **once** (lazily via DI Singleton) from JSON files. No runtime reloading.
3. Version lookup is **case-sensitive** — `ARA` and `ara` are different keys.
4. Endpoints are **public** — no authentication required.
5. When `headings` is present, it must have one entry per chapter, and every heading's `verse` must exist in its chapter. A file that breaks this fails to load at startup.

## Errors

| Scenario               | Error                          |
|------------------------|--------------------------------|
| Unknown version name   | `BibleVersionNotFound` (→ 404) |

---

# Bible Videos (feature 025)

YouTube videos and playlists linked by leadership to chapters and/or whole books, listed for
everyone in the reader. Design and reasons: `specs/025-bible-videos/`.

## Book identifier

The book's `abbrev` exactly as served above (`Gn`, `Êx`, `Jó`, `1Tn` — 66 books, canonical
order). Both translations share the same books and chapter counts, so videos and progress do not
depend on the translation; startup fails if they ever disagree. Input is matched ignoring case
(`gn` finds `Gn`; accents still matter, so `Jo` and `Jó` stay distinct) and always stored and
returned canonically.

## Data Model (database)

### BibleVideo

| Field | Type | Notes |
|---|---|---|
| `id` | int | |
| `kind` | `video` \| `playlist` | |
| `youtube_id` | str | video id (11 chars) or playlist id; unique together with `kind` |
| `url` | str | canonical URL built by the server |
| `title` | str | read from YouTube once, on save; never edited nor refreshed |
| `thumbnail_url` | str | `https://i.ytimg.com/vi/<id>/hqdefault.jpg` for videos, YouTube's own for playlists |
| `created_by` | user, nullable | kept null when the user is deleted |
| `created_at`, `updated_at` | datetime | |

### BibleVideoPlace

`video`, `book`, `chapter` (null = whole book), `position` (order inside that place, from 0).
A video appears at most once per place. A range is not a concept: "Gn 1–3" is three places.
A video with no places is deleted.

### BibleChapterProgress / BibleVideoProgress

Per user: (`book`, `chapter`) or `video`, `done`, `changed_at` (client time of the change, UTC).
One row per target. `done=false` rows are kept as tombstones so an older offline "mark" cannot
bring back something unmarked later. "Book read" is not stored — the app derives it. Deleted with
the user; video progress is deleted with the video.

## Video endpoints

| Method and path | Access | Body | Success |
|---|---|---|---|
| `GET /api/bible/videos/` | public | — | 200 list, ETag/304 |
| `POST /api/bible/videos/` | `bible_videos` manage | `{"url", "places": [{"book", "chapter"}]}` (≥ 1) | 201 video |
| `PUT /api/bible/videos/{id}/places/` | manage | `{"places": [...]}` | 200 video; 204 when empty (video deleted) |
| `DELETE /api/bible/videos/{id}/places/?book=Gn&chapter=1` | owner | — (`chapter` absent = whole book) | 200 video; 204 when it was the last place |
| `DELETE /api/bible/videos/{id}/` | owner | — | 204 |
| `PUT /api/bible/videos/order/` | manage | `{"book", "chapter", "video_ids"}` (`chapter` null = book) | 204 |

Video object:

```json
{"id": 42, "kind": "video", "youtube_id": "dQw4w9WgXcQ",
 "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=90", "title": "...",
 "thumbnail_url": "https://i.ytimg.com/vi/dQw4w9WgXcQ/hqdefault.jpg",
 "places": [{"book": "Gn", "chapter": null, "position": 0}, {"book": "Gn", "chapter": 1, "position": 2}]}
```

The list is ordered by video id; places by canonical book order, whole book first, then chapter.

### Rules

1. Accepted links: `youtube.com/watch?v=`, `youtu.be/`, `youtube.com/shorts/`, `youtube.com/live/`
   (hosts `youtube.com`, `www.`, `m.`, `music.`) as videos; `youtube.com/playlist?list=` as
   playlists. `watch?v=X&list=Y` is the video X. A start time (`t=90`, `1m30s`) is kept in the
   URL as seconds. Anything else is refused.
2. One video per (kind, YouTube id): saving it again answers 409 with the existing video, before
   any call to YouTube.
3. Title and thumbnail come from YouTube oEmbed (no key, 5 s timeout). Private, removed or
   non-embeddable → refused; timeout or YouTube failure → 503, retry later.
4. New places go to the end of their place (`max + 1`). Replacing the places keeps the position of
   the ones that stay. Reordering one place sets 0..n-1 and touches no other place; the list must
   be exactly the videos of that place.
5. Liderança and Admin hold `owner` on `bible_videos`; Mídia nothing.

## Progress endpoints (signed in, no scope)

- `GET /api/bible/progress/` → `{"chapters": {"Gn": [1, 2]}, "videos": [42]}` — done items only;
  private ETag.
- `POST /api/bible/progress/sync/` with `{"changes": [...]}`, 1–500 items:
  `{"type": "chapter", "book", "chapter", "done", "changed_at"}` or
  `{"type": "video", "video_id", "done", "changed_at"}` → 200
  `{"accepted": [indexes], "rejected": [{"index", "reason"}]}`.

### Rules

1. A change applies only when there is no row for its target or its `changed_at` is strictly
   later than the stored one; older changes are accepted and ignored (last write wins by the time
   of the action, not arrival order). Items for the same target inside one batch follow the same
   rule in order.
2. Per-item rejections: `unknown_book`, `unknown_chapter`, `unknown_video`,
   `changed_at_without_offset`, `changed_at_in_future` (more than 5 minutes ahead).
3. Shape errors (unknown or missing field, wrong type, unknown `type`, 0 or > 500 items) refuse the
   whole batch with 400 `VALIDATION_ERROR`.

## Video and progress errors

| Code | Status | When |
|---|---|---|
| `BIBLE_VIDEO_INVALID_URL` | 400 | Not a supported YouTube video/playlist link |
| `BIBLE_VIDEO_UNAVAILABLE` | 400 | YouTube says private/removed/not embeddable |
| `BIBLE_VIDEO_LOOKUP_FAILED` | 503 | YouTube timeout or failure |
| `BIBLE_VIDEO_EXISTS` | 409 | Same video already saved; body adds `video` |
| `BIBLE_PLACE_INVALID` | 400 | Unknown book, chapter out of range, repeated place, no place |
| `BIBLE_VIDEO_ORDER_MISMATCH` | 400 | Order is not exactly the place's videos; body adds `expected_video_ids` |
| `BIBLE_VIDEO_NOT_FOUND` | 404 | Unknown video id |
| `BIBLE_PLACE_NOT_FOUND` | 404 | Removing a place the video is not in |

Out of scope: reading plans, percentages, streaks, reports; progress without login; title editing
or metadata refresh; push about new videos.
