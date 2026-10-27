# Data Model: Bible Videos and Reading Progress

App label `bible` (`features/bible/models/`). Generated migration `bible/0001_initial`.
Book values are canonical identifiers (`Gn`, `Êx`, ...), max length 8.

## BibleVideo (`bible_video.py`)

| Field | Type | Notes |
|---|---|---|
| `id` | auto | |
| `kind` | char(10), choices `video`/`playlist` | |
| `youtube_id` | char(64) | video id (11) or playlist id |
| `url` | char(300) | canonical URL built by the server |
| `title` | char(300) | from oEmbed; cut to length |
| `thumbnail_url` | char(500) | |
| `created_by` | FK user, null, `SET_NULL`, `related_name="+"` | auditing |
| `created_at` / `updated_at` | datetime auto | |

Constraints: unique (`kind`, `youtube_id`) `bible_video_unique_youtube_target`.
Ordering `["id"]`. `__str__` → title.

## BibleVideoPlace (`bible_video.py`)

| Field | Type | Notes |
|---|---|---|
| `id` | auto | |
| `video` | FK `BibleVideo`, `CASCADE`, `related_name="places"` | |
| `book` | char(8) | canonical identifier |
| `chapter` | positive smallint, null | null = whole book |
| `position` | positive int | order inside (book, chapter) |

Constraints:
- unique (`video`, `book`, `chapter`) with `condition=Q(chapter__isnull=False)` —
  `bible_place_unique_chapter`;
- unique (`video`, `book`) with `condition=Q(chapter__isnull=True)` — `bible_place_unique_book`
  (SQL treats NULLs as distinct, so the whole-book case needs its own constraint).

Index (`book`, `chapter`, `position`). Ordering `["book", "chapter", "position", "video_id"]`.

## BibleChapterProgress (`bible_progress.py`)

| Field | Type | Notes |
|---|---|---|
| `user` | FK user, `CASCADE`, `related_name="+"` | |
| `book` | char(8) | |
| `chapter` | positive smallint | |
| `done` | bool | false rows are tombstones |
| `changed_at` | datetime | client time of the change, stored UTC |

Unique (`user`, `book`, `chapter`) `bible_chapter_progress_unique`. Ordering
`["user_id", "book", "chapter"]`.

## BibleVideoProgress (`bible_progress.py`)

| Field | Type | Notes |
|---|---|---|
| `user` | FK user, `CASCADE` | |
| `video` | FK `BibleVideo`, `CASCADE`, `related_name="+"` | |
| `done` | bool | |
| `changed_at` | datetime | |

Unique (`user`, `video`) `bible_video_progress_unique`. Ordering `["user_id", "video_id"]`.

## DTOs (`features/bible/video_dtos.py`, `progress_dtos.py`)

- `BiblePlaceDTO(book: str, chapter: int | None)` — input place (book not yet canonical).
- `BibleVideoPlaceDTO(book, chapter, position)` — output.
- `BibleVideoDTO(id, kind, youtube_id, url, title, thumbnail_url, places)`.
- `YouTubeTargetDTO(kind, youtube_id, url)` — parsed link.
- `YouTubeMetadataDTO(title, thumbnail_url)`.
- `BibleVideoCreateDTO(url: str, places: list[BiblePlaceDTO])`, `BibleVideoPlacesDTO(places)`,
  `BibleVideoOrderDTO(book, chapter, video_ids)`.
- `ChapterChangeDTO(type="chapter", book, chapter, done, changed_at)`,
  `VideoChangeDTO(type="video", video_id, done, changed_at)`, `ProgressSyncDTO(changes)` (1–500,
  discriminated on `type`).
- `ProgressStateDTO(chapters: dict[str, list[int]], videos: list[int])`,
  `ProgressSyncResultDTO(accepted: list[int], rejected: list[RejectedChangeDTO])`.
- `ChapterMarkDTO(book, chapter, done, changed_at)`, `VideoMarkDTO(video_id, done, changed_at)` —
  rows between repository and service.

## State rules

- A video exists only while it has at least one place (service enforces on every place removal).
- A progress row is only ever overwritten by a strictly later `changed_at`.
