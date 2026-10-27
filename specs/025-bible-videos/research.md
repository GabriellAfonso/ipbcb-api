# Research: Bible Videos and Reading Progress

Decisions taken in the design conversation are in the spec; these are the plan-level choices.

## R-01 — Everything lives in `features/bible`

- **Decision**: models, repositories, services, views of videos and progress go in
  `features/bible`, which gains a `models` package and its first migrations. Only the new scope
  (`core/domain/access.py`), its data migration and the exceptions go to `core`.
- **Rationale**: both capabilities hang on the Bible's books and chapters; features never import
  each other (constitution), and nothing here is shared with another feature.
- **Alternatives**: a new `bible_videos` app — rejected, it would need the book catalogue from
  `bible` (a cross-feature import).

## R-02 — Book catalogue (`BibleCanon`) from the loaded translations

- **Decision**: a pure `BibleCanon` (`features/bible/domain/canon.py`) holds the 66 canonical
  identifiers in order, their chapter counts and a case-insensitive lookup. `BibleRepository`
  gains `canon()`, built once from the loaded files; loading fails if the translations disagree on
  books or chapter counts, or if two identifiers collide ignoring case.
- **Rationale**: the data has no database model; the identifiers are the served `abbrev` (`Gn`,
  `Êx`, `1Tn`), not lowercase ASCII as the saved request assumed (spec, Definitions).
  `str.casefold()` keeps `Jó` and `Jo` distinct (accent) while `gn` finds `Gn`.
- **Alternatives**: a hand-written list of 66 books — rejected, a second source of truth.

## R-03 — YouTube link parsing is pure

- **Decision**: `features/bible/domain/youtube_links.py` parses with `urllib.parse`. Hosts:
  `youtube.com`, `www.`, `m.`, `music.` and `youtu.be`. Video ids match `[A-Za-z0-9_-]{11}`;
  playlist ids `[A-Za-z0-9_-]{10,64}`. `watch?v=X&list=Y` is the video X. `t`/`start` accepts
  `90`, `90s`, `1m30s`, `1h2m3s`; stored as seconds in the canonical URL (`&t=90`). Scheme-less
  links (`youtu.be/x`) are accepted by prefixing `https://`.
- **Rationale**: testable without network; the canonical URL is what makes the duplicate check
  independent of how the link was pasted.

## R-04 — oEmbed behind a project-owned port

- **Decision**: `YouTubeMetadataClient` protocol, implemented by `HttpYouTubeOEmbedClient` over
  `requests` (already a dependency, as in `HttpAvatarDownloader`), timeout 5 s. HTTP 400/401/403/
  404 → `BibleVideoUnavailableError`; timeout, connection error, other status or unparseable body
  → `BibleVideoLookupFailedError`. Title is trimmed and cut to the column size.
- **Rationale**: CLAUDE.md §7 (wrap third-party libs); tests use `FakeYouTubeMetadataClient`.
  YouTube answers 400 for a malformed or nonexistent playlist id, so 400 means "unavailable".

## R-05 — 503 needs a new base exception

- **Decision**: `UpstreamUnavailableError(DomainError)` in `core/domain/base_exceptions.py`,
  mapped to 503 in `core/http/exceptions.py`. Bible exceptions live in
  `core/domain/bible_exceptions.py`, re-exported by `core/domain/exceptions.py` (500-line rule).
- **Rationale**: no existing family maps to 503; a lookup failure is retryable, unlike 400/500.

## R-06 — Duplicate check before the lookup; 409 carries the video

- **Decision**: the service parses the link, asks the repository for (kind, youtube_id); found →
  `BibleVideoExistsError(video_body)` whose `extra_context()` is `{"video": {...}}`. Only then the
  oEmbed call. A unique-violation on insert (race between two leaders) is mapped to the same
  error by re-reading the row.
- **Rationale**: no wasted network call; the app needs the existing video to open its places.

## R-07 — Positions

- **Decision**: appending computes `max(position) + 1` per affected place in one grouped query
  inside the write transaction; empty place → 0. Reading orders by `(position, video_id)`.
  Reorder writes positions `0..n-1` with one `bulk_update`.
- **Rationale**: two concurrent appends may tie; the tie-break keeps output stable and the next
  reorder normalises (spec edge case). Locking for this is not worth it at this volume.

## R-08 — Progress sync: last write wins in memory, one upsert

- **Decision**: per batch, the service loads the user's rows for the targeted chapters and videos
  (two queries), checks unknown videos (one query), folds the changes in order applying "strictly
  newer `changed_at` wins", then writes the winners with `bulk_create(update_conflicts=True,
  unique_fields=..., update_fields=["done", "changed_at"])` — one statement per table, all in one
  transaction.
- **Rationale**: no queries in loops; FR-023 (same target twice in one batch) falls out of the
  fold. Two simultaneous syncs of the same user could interleave between read and write; the
  later change still wins on the next sync of either device, and the window is milliseconds.
- **Alternatives**: a conditional `UPDATE ... WHERE changed_at < new` per item — exact under
  concurrency but one query per item (up to 500).

## R-09 — Per-item validation without breaking strict DTOs

- **Decision**: the body is validated whole by strict Pydantic DTOs (`extra="forbid"`, a
  discriminated union on `type`, 1–500 items): any shape error → 400 `VALIDATION_ERROR`.
  `changed_at` is parsed as `datetime` and its offset checked by the service (per item,
  `changed_at_without_offset`), together with book, chapter, video and future checks.
- **Rationale**: spec FR-020/FR-022: shape is the client's bug (whole batch), values are per item.
  Future tolerance 5 min against the injected `Clock`.

## R-10 — Routes and ordering

- **Decision**: the new routes are declared before `api/bible/<str:name>/` in
  `features/bible/urls.py`, else `videos` and `progress` would be read as a translation name.
  Removing one place uses query parameters (`?book=Gn&chapter=1`; `chapter` absent = whole book):
  DELETE bodies are dropped by some HTTP clients.
- **Rationale**: same router; no new prefix.

## R-11 — Public list with ETag

- **Decision**: `_not_modified_or_response(request, body)` without `private` — the list is the
  same for everyone, so a cache in front may store it.

## R-12 — Scope and migrations

- **Decision**: `Scope.BIBLE_VIDEOS = "bible_videos"`. `makemigrations core` generates the
  `PanelScope` options change (like 0009); a hand-written data migration gives Liderança
  `bible_videos__owner` (shape of 0010; reverse removes it). The access matrix test gains the
  scope's rows.
- **Rationale**: spec FR-001.
