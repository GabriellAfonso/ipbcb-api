# API Contract: Bible Videos and Reading Progress

All paths under the `/ipbcb/` prefix in production. Errors use `{"error_code", "detail"}`
(spec 001). Book identifiers are matched ignoring case and returned canonically (`Gn`, `Êx`).

## Video object

```json
{"id": 42, "kind": "video", "youtube_id": "dQw4w9WgXcQ",
 "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=90", "title": "Gênesis 1 — estudo",
 "thumbnail_url": "https://i.ytimg.com/vi/dQw4w9WgXcQ/hqdefault.jpg",
 "places": [{"book": "Gn", "chapter": null, "position": 0}, {"book": "Gn", "chapter": 1, "position": 2}]}
```

Places are ordered by canonical book order, whole book first, then chapter.

## `GET api/bible/videos/` — public

200: array of video objects, ordered by id. `ETag`; `If-None-Match` match → 304.

## `POST api/bible/videos/` — `bible_videos` manage

Body `{"url": "https://youtu.be/dQw4w9WgXcQ?t=90", "places": [{"book": "gn", "chapter": 1}]}`.
201: video object. 400 `BIBLE_VIDEO_INVALID_URL` | `BIBLE_PLACE_INVALID` |
`BIBLE_VIDEO_UNAVAILABLE` | `VALIDATION_ERROR`; 409 `BIBLE_VIDEO_EXISTS` with `"video": {...}`;
503 `BIBLE_VIDEO_LOOKUP_FAILED`; 401/403.

## `PUT api/bible/videos/{id}/places/` — manage

Body `{"places": [{"book": "Gn", "chapter": 2}, {"book": "Êx", "chapter": null}]}`.
200: video object; 204 when `places` is empty (video deleted). 400 `BIBLE_PLACE_INVALID`;
404 `BIBLE_VIDEO_NOT_FOUND`.

## `DELETE api/bible/videos/{id}/places/?book=Gn&chapter=1` — owner

`chapter` absent = the whole-book place. 200: video object; 204 when it was the last place.
400 `BIBLE_PLACE_INVALID` (unknown book, chapter out of range) | `VALIDATION_ERROR` (no `book`,
non-integer `chapter`); 404 `BIBLE_VIDEO_NOT_FOUND` |
`BIBLE_PLACE_NOT_FOUND`.

## `DELETE api/bible/videos/{id}/` — owner

204. 404 `BIBLE_VIDEO_NOT_FOUND`.

## `PUT api/bible/videos/order/` — manage

Body `{"book": "Gn", "chapter": 1, "video_ids": [3, 7, 42]}` (`chapter` null = book list).
204. 400 `BIBLE_PLACE_INVALID` | `BIBLE_VIDEO_ORDER_MISMATCH` (body adds `"expected_video_ids"`).

## `GET api/bible/progress/` — signed in

200 `{"chapters": {"Gn": [1, 2, 3], "Rm": [5]}, "videos": [7, 42]}` — only done items; books in
canonical order, chapters and video ids ascending. Private ETag.

## `POST api/bible/progress/sync/` — signed in

```json
{"changes": [
  {"type": "chapter", "book": "Gn", "chapter": 1, "done": true, "changed_at": "2026-10-27T10:00:00-03:00"},
  {"type": "video", "video_id": 42, "done": false, "changed_at": "2026-10-27T10:01:00-03:00"}]}
```

1–500 items. 200 `{"accepted": [0], "rejected": [{"index": 1, "reason": "unknown_video"}]}` —
every index appears exactly once. Reasons: `unknown_book`, `unknown_chapter`, `unknown_video`,
`changed_at_without_offset`, `changed_at_in_future`. 400 `VALIDATION_ERROR` for shape errors
(unknown/missing field, wrong type, unknown `type`, size).
