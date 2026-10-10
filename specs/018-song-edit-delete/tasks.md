---

description: "Task list for feature 018 — edit and delete songs"
---

# Tasks: Edit and Delete Songs

**Input**: Design documents from `specs/018-song-edit-delete/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/song-detail-api.md, quickstart.md

**Tests**: requested by the feature description and required by CLAUDE.md §10, so they are included.
Unit tests use named fakes; integration tests use the real SQLite test database.

**Organization**: grouped by user story. US1 = edit (P1), US2 = delete a free song (P2), US3 = refused
delete with explanation (P2, builds on US2's endpoint).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1, US2, US3 (spec.md user stories)
- Paths are relative to the repository root. Tests and commands run from `server/`, with
  `.venv_windows` active.

## Constraints that apply to every task

- **mypy strict runs over the whole `server/` tree, tests included**, on every commit. When a method
  is added to the `SongRepository` protocol (`server/features/songs/repositories/interfaces.py`), add it
  to `SongRepositoryImpl` and to `FakeSongRepository` in the same task and commit.
- Functions 4–20 lines, max 2 levels of indentation, a docstring with intent plus one example on
  public functions, and exception messages that name the offending value (CLAUDE.md §8–9).
- Keep existing comments when moving code (CLAUDE.md §9).
- Before shipping, `specs/songs/spec.md`, the spec 012 classification and the code go in the same
  commit (CLAUDE.md §6.2).
- **No role holds `view` on `songs`** (spec 012 scope matrix: Admin owner, Liderança manage, Mídia
  none), and the constitution says only roles grant levels. Wherever the description says "403
  with `view`", test it with `make_role_client(Role.MEDIA)`.

---

## Phase 1: Setup

**Purpose**: know the baseline before touching anything.

- [X] T001 Run `pytest features/songs core/tests/integration/test_management_access_matrix.py` from `server/` and record that it is green before any change; also run `python -m mypy .` from `server/` and record that it is clean

---

## Phase 2: Foundational (blocking prerequisites)

**Purpose**: the not-found error and the in-memory fake that both edit and delete need.

- [X] T002 Add `SongNotFoundError(NotFoundError)` to `server/core/domain/exceptions.py`, right after `SongsNotFoundError`, following `ChordChartNotFoundError`: `__init__(self, song_id: int)` with message `f"Song not found: id={song_id}"`, attribute `song_id`, `extra_context()` returning `{"song_id": self.song_id}`, and a docstring saying it is the single-id case while `SongsNotFoundError` stays the batch case
- [X] T003 [P] Create `server/features/songs/tests/unit/test_song_exceptions.py` with a test class for `SongNotFoundError`: `error_code == "NOT_FOUND"`, `str(exc) == "Song not found: id=7"`, `extra_context() == {"song_id": 7}`
- [X] T004 Add `FakeSongRepository` to `server/features/songs/tests/fakes.py`. It is an in-memory implementation of the **whole** current `SongRepository` protocol, holding unsaved `Song` instances in a `dict[int, Song]` given to the constructor. `get_song_by_id` returns from the dict. Every method these tests do not exercise raises `NotImplementedError(f"FakeSongRepository.<name> is not used by these tests")`. Record calls in a `calls: list[str]` attribute, so tests can assert that a query did *not* run. The class docstring says it exists because mypy checks tests against the full protocol

**Checkpoint**: `pytest features/songs` and `python -m mypy .` are green.

---

## Phase 3: User Story 1 — Fix a typo in a catalogue song (Priority: P1) 🎯 MVP

**Goal**: `PATCH api/songs/{id}/` edits `title`, `artist` and/or `youtube_link` with the create rules,
refuses a new duplicate pair, and answers the song in list shape.

**Independent Test**: create a song, `PATCH` only `title` as Liderança, and check that the response and
`GET api/songs/` show the new title while artist, link and category are unchanged.

### Implementation and tests for User Story 1

- [X] T005 [US1] In `server/features/songs/dtos.py`, extract the link rule into a shared type. Turn `NewSongInput.youtube_link_is_url` into a module-level function `_require_http_url(v: str) -> str`, keeping its comment ("Validated but stored as typed: HttpUrl would normalize it…"). Declare `_YoutubeLink = Annotated[str, StringConstraints(strip_whitespace=True), Field(max_length=200), AfterValidator(_require_http_url)]` next to `_SongText`. Change `NewSongInput.youtube_link` to `_YoutubeLink = ""` and delete the method. Keep the error text `youtube_link must be an http(s) URL; got {v!r}`. Then run `pytest features/songs/tests/unit/test_new_song_input.py features/songs/tests/integration/test_songs_api.py` **unmodified**: it is the regression proof (research R-01)
- [X] T006 [US1] In `server/features/songs/dtos.py`, add `SongChangesInput(StrictBaseModel)` per data-model.md:
  - `title: _SongText | None = None`, `artist: _SongText | None = None` and `youtube_link: _YoutubeLink | None = None`.
  - A `field_validator("title", "artist", "youtube_link", mode="before")` that raises `ValueError(f"{info.field_name} must not be null; omit the field to keep it")` when the value is `None`.
  - A `model_validator(mode="after")` that raises `ValueError("send at least one of: title, artist, youtube_link")` when `model_fields_set` is empty.
  - A docstring with an example, e.g. `SongChangesInput(title=" Oceans ")`.
- [X] T007 [P] [US1] Create `server/features/songs/tests/unit/test_song_changes_input.py`. Cover: each field alone, trimmed; `youtube_link=""` accepted and in `model_fields_set`; `null` for each field rejected (the error `loc` names the field); `{}` rejected; `category` and an unknown key rejected (`extra_forbidden`); title/artist of 101 characters after trimming rejected; whitespace-only title rejected; a non-http link and a 201-character link rejected; `model_dump(exclude_unset=True)` holds only the keys sent
- [X] T008 [US1] Extend the repository for edit (protocol, implementation and fake in one task, per the mypy constraint):
  - In `server/features/songs/repositories/interfaces.py`, change `song_exists(self, title: str, artist: str, exclude_id: int | None = None) -> bool` and add `update_song(self, song: Song, changes: SongChangesInput) -> Song`.
  - In `server/features/songs/repositories/song_repository.py`, `song_exists` adds `.exclude(pk=exclude_id)` when `exclude_id is not None`. `update_song` applies `changes.model_dump(exclude_unset=True)` with `setattr`, then calls `save(update_fields=[...those keys])` and returns the song.
  - In `server/features/songs/tests/fakes.py`, `FakeSongRepository` implements both in memory (case-insensitive compare, skipping `exclude_id`) and appends `"song_exists"` / `"update_song"` to `calls`.
  - `create_song`'s call in `SongService.create_song` keeps working unchanged.
- [X] T009 [US1] In `server/features/songs/services/song_service.py`, add the edit logic:
  - `update_song(self, song_id: int, changes: SongChangesInput) -> Song`: fetch with `get_song_by_id` and raise `SongNotFoundError(song_id)` when it is missing. Compute the resulting `title` / `artist` (the change, or the stored value). When `_pair_changed(song, title, artist)` is true and `self._repository.song_exists(title, artist, exclude_id=song.pk)`, raise `DuplicateSongError(title, artist)`. Otherwise return `self._repository.update_song(song, changes)`.
  - `_pair_changed` is a module-level pure function comparing `(x.strip().lower(), y.strip().lower())` of stored vs resulting values.
  - The docstring states that the check only runs when the normalized pair changes (spec FR-005, clarification Q1, research R-03), and notes the accepted race as `create_song` does.
- [X] T010 [P] [US1] Create `server/features/songs/tests/unit/test_song_service_update.py`, using `FakeSongRepository`:
  - Editing only the title, only the artist, or only the link changes only that field.
  - `youtube_link=""` clears the link.
  - Renaming onto another song's pair, in different case and with spaces, raises `DuplicateSongError` carrying the sent `title`/`artist`, and `update_song` is not in `calls`.
  - Saving the same values, or a case-only change (`"oceans"` → `"Oceans"`), succeeds and `song_exists` is **not** in `calls`.
  - A link-only edit on a song whose pair repeats another stored song succeeds.
  - An unknown id raises `SongNotFoundError`.
- [X] T011 [US1] In `server/features/songs/views/songs.py`, add `SongDetailAPI(APIView)` after `AllSongsAPI`, with `permission_classes = [IsAuthenticated, scope_permission(Scope.SONGS)]` (no overrides, like `ChordChartDetailAPI`). Its `@inject patch(self, request, pk: int, song_service=Provide[Container.song_service])` calls `song_service.update_song(pk, SongChangesInput.model_validate(request.data))` and returns `Response(SongSerializer(song).data)`. Reuse the same comment style as `AllSongsAPI.post` about pydantic errors becoming a 400
- [X] T012 [US1] In `server/features/songs/urls.py`, import `SongDetailAPI` and add `path("api/songs/<int:pk>/", SongDetailAPI.as_view(), name="song_detail")` right after `all_songs`
- [X] T013 [US1] Create `server/features/songs/tests/integration/test_song_detail_api.py` with class `TestEditSongAPI`, using `make_role_client(Role.LEADER)` as the `manage` caller:
  - `200` with exactly `{id, title, artist, category, youtube_link}`, with `category` the name or `""`.
  - Partial edit leaves the other fields unchanged in the DB.
  - `youtube_link: ""` clears it.
  - `400 VALIDATION_ERROR` with `field_errors` for `{}`, `{"category": "x"}`, `{"title": null}` and a non-URL link.
  - `409 CONFLICT` with `title`/`artist` in the body against another song.
  - Case-only change gives `200`.
  - `404` with `song_id` for an unknown id.
  - `401` anonymous.
  - `403` for `make_role_client(Role.MEDIA)`.
- [X] T014 [US1] In the same file, add class `TestSongDataCachesAfterEdit` (spec FR-018, research R-08). For each of `/api/songs/`, `/api/songs-by-sunday/` and `/api/top-songs/` (song with one `Played` row): GET, keep the `ETag`, PATCH the title, then GET with `HTTP_IF_NONE_MATCH=<old etag>` and assert `200` with the new title in the body

**Checkpoint**: US1 is a shippable MVP. `PATCH` works end-to-end, and `DELETE` answers `405`.

---

## Phase 4: User Story 2 — Delete a song registered by mistake (Priority: P2)

**Goal**: `DELETE api/songs/{id}/` as `owner` removes an unreferenced song together with its chord charts
and lyrics.

**Independent Test**: create a song with a chord chart and lyrics, `DELETE` it as Admin → `204`, and the
three rows are gone. As Liderança → `403`.

### Implementation and tests for User Story 2

- [X] T015 [US2] Add `delete_song(self, song: Song) -> None` to the `SongRepository` protocol in `server/features/songs/repositories/interfaces.py`. In `server/features/songs/repositories/song_repository.py`, implement it as `with transaction.atomic(): song.delete()` (the in-use translation comes in US3). Implement it in `FakeSongRepository` in `server/features/songs/tests/fakes.py` by removing from the dict and appending `"delete_song"` to `calls`. All in one task, per the mypy constraint
- [X] T016 [US2] In `server/features/songs/services/song_service.py`, add `delete_song(self, song_id: int) -> None`: fetch or raise `SongNotFoundError(song_id)`, then `self._repository.delete_song(song)`. Include a docstring with an example
- [X] T017 [P] [US2] Create `server/features/songs/tests/unit/test_song_service_delete.py` using `FakeSongRepository`: a free song is removed and `delete_song` is in `calls`; an unknown id raises `SongNotFoundError` and nothing is deleted
- [X] T018 [US2] In `server/features/songs/views/songs.py`, add `@inject delete(self, request, pk: int, song_service=Provide[Container.song_service])` to `SongDetailAPI`, calling `song_service.delete_song(pk)` and returning `Response(status=204)`
- [X] T019 [US2] In `server/features/songs/tests/integration/test_song_detail_api.py`, add class `TestDeleteSongAPI`:
  - Admin (`make_admin_client()`) deletes a free song that has one `ChordChart` and one `Lyrics`: `204`, empty body, and `Song`, `ChordChart` and `Lyrics` counts for it are 0.
  - `404` with `song_id` for an unknown id.
  - `401` anonymous.
  - `403` for `Role.MEDIA`.
  - `403` for `Role.LEADER` (manage is not enough), with the song still present.

**Checkpoint**: deleting a free song works. Deleting a song in use still raises `ProtectedError` (500) until US3 is done, so **do not ship US2 without US3**.

---

## Phase 5: User Story 3 — Understand why a song cannot be deleted (Priority: P2)

**Goal**: a song with plays and/or on a setlist is never deleted. The answer is `409` with the pt-BR
`detail` and `{song_id, title, plays, setlist_dates}`, including when the reference appears during the
delete.

**Independent Test**: give a song plays on two dates (one date twice) and a setlist item, `DELETE` as
Admin, and check the `409` message and data per the contract. Song, plays, setlist, chord charts and
lyrics are all unchanged.

### Implementation and tests for User Story 3

- [X] T020 [US3] Add `SongInUseError(ConflictError)` to `server/core/domain/exceptions.py`, after `SongNotFoundError`, per research R-06 and the wording table in `specs/018-song-edit-delete/contracts/song-detail-api.md`:
  - `__init__(self, song_id: int, title: str, plays: int, setlist_dates: list[date])`.
  - The message is `f'A música "{title}" não pode ser excluída: {reasons}.'`, where `reasons` comes from small module-level helpers:
    - `_plays_reason(plays)` gives `foi tocada em 1 domingo` / `foi tocada em N domingos`, or nothing at 0.
    - `_setlist_reason(dates)` gives `está na setlist de DD/MM/AAAA` / `está nas setlists de A, B e C`, or nothing when empty.
    - `_join_pt(parts)` joins with `, ` and a final ` e `.
  - `extra_context()` returns `{"song_id", "title", "plays", "setlist_dates": [d.isoformat() ...]}`.
  - The docstring explains why the message is pt-BR (shown in the app, unlike `ServiceInUseError`).
- [X] T021 [P] [US3] In `server/features/songs/tests/unit/test_song_exceptions.py`, add a test class for `SongInUseError` with one test per row of the contract's wording table (1 play; 7 plays; one setlist date; two dates; three dates; plays + setlist). Also test `error_code == "CONFLICT"` and `extra_context()` with ISO date strings
- [X] T022 [US3] In `server/features/songs/dtos.py`, add `SongUsage(StrictBaseModel)` with `plays: int`, `setlist_dates: list[date]` and an `in_use` property (`plays > 0 or bool(setlist_dates)`), plus a docstring with an example
- [X] T023 [US3] Add `get_song_usage(self, song_id: int) -> SongUsage` to the `SongRepository` protocol in `server/features/songs/repositories/interfaces.py`. Implement it in `server/features/songs/repositories/song_repository.py` per research R-04:
  - `Played.objects.filter(song_id=song_id).values("date").distinct().count()`.
  - `SetlistItem.objects.filter(song_id=song_id).values_list("setlist__date", flat=True).distinct().order_by("setlist__date")`, importing `SetlistItem` from `features.songs.models.setlist`.
  - Implement it in `FakeSongRepository` (`server/features/songs/tests/fakes.py`) from a `usage: dict[int, SongUsage]` constructor argument (default: not in use). Append `"get_song_usage"` to `calls`.
  - All in one task.
- [X] T024 [US3] In `server/features/songs/repositories/song_repository.py`, add the race translation per research R-05, following `_translate_duplicate` in `server/features/gallery/repositories/album_repository.py`:
  - A `@contextmanager` method `_translate_in_use(self, song: Song) -> Iterator[None]` wraps `with transaction.atomic(): yield`.
  - On `ProtectedError` or `IntegrityError` it re-reads `self.get_song_usage(song.pk)`. When `usage.in_use`, it raises `SongInUseError(song.pk, song.title, usage.plays, usage.setlist_dates) from exc`; otherwise it re-raises the original.
  - `delete_song` becomes `with self._translate_in_use(song): song.delete()`.
  - The docstring explains both exceptions: the collector's `PROTECT`, and PostgreSQL's deferred FK at commit (`ATOMIC_REQUESTS` is off, so this block is the outermost).
- [X] T025 [US3] In `server/features/songs/services/song_service.py`, update `delete_song`: after the lookup, read `usage = self._repository.get_song_usage(song.pk)`, and when `usage.in_use` raise `SongInUseError(song.pk, song.title, usage.plays, usage.setlist_dates)` before calling `delete_song`. The docstring mentions that the repository covers the race
- [X] T026 [P] [US3] In `server/features/songs/tests/unit/test_song_service_delete.py`, add tests:
  - Blocked by plays only, by setlist only, and by both: each raises `SongInUseError` with the expected message and `extra_context()`, and `delete_song` is **not** in `calls`.
  - A free song (usage default) is deleted.
- [X] T027 [US3] Create `server/features/songs/tests/integration/test_song_repository_delete.py` (real DB) with these tests:
  - (a) **Real `ProtectedError` race**. Add `BlindUsageSongRepository(SongRepositoryImpl)` to `server/features/songs/tests/fakes.py`. It reports `SongUsage(plays=0, setlist_dates=[])` only on its first `get_song_usage` call, which simulates a play committed after the service's check, and delegates afterwards. Build `SongService(BlindUsageSongRepository())` for a song with a `Played` row and call `delete_song`. Assert `SongInUseError` with `plays == 1`, and that the song and its `Played` row still exist.
  - (b) **`IntegrityError` translation**. With a `Played` row present, `with pytest.raises(SongInUseError): with repo._translate_in_use(song): raise IntegrityError("FOREIGN KEY constraint failed")`.
  - (c) **Unrelated `IntegrityError` re-raised** for a free song.
  - (d) **Distinct counts**. A song played twice on one date and once on another, and on two setlists, gives `get_song_usage == SongUsage(plays=2, setlist_dates=[d1, d2])` in ascending order.
- [X] T028 [US3] In `server/features/songs/tests/integration/test_song_detail_api.py`, add class `TestBlockedDeleteAPI` (Admin client):
  - A song with plays and a setlist on `2026-10-18` gives `409` with `error_code == "CONFLICT"`, the exact pt-BR `detail`, `song_id`, `title`, `plays` and `setlist_dates == ["2026-10-18"]`.
  - Plays only, and setlist only, each give `detail` mentioning only that reason.
  - After every blocked delete, `Song`, `Played`, `Setlist`/`SetlistItem`, `ChordChart` and `Lyrics` counts are unchanged.
  - Create setlists with the ORM directly (`Setlist.objects.create(date=..., saved_at=...)` plus `SetlistItem`); the worship-member setup of the setlist API is not needed.

**Checkpoint**: all three stories work. `DELETE` never answers 5xx.

---

## Phase 6: Polish & cross-cutting

- [X] T029 [P] In `specs/songs/spec.md`, add `### PATCH /api/songs/{id}/` and `### DELETE /api/songs/{id}/` right after `### POST /api/songs/`, in the same style (Auth, Request body, Response, Errors), linking `specs/018-song-edit-delete/contracts/song-detail-api.md` for the full wording table. In Architecture, mention `SongService` song edit/delete. In Design Decisions, add a bullet: the duplicate check on edit only runs when the normalized pair changes, and a song in use cannot be deleted (no soft delete)
- [X] T030 [P] In `specs/012-feature-role-permissions/spec.md`, in the `### songs` table of Endpoint Classification, add `| PATCH | \`api/songs/{id}/\` | \`songs\` | manage | default |` and `| DELETE | \`api/songs/{id}/\` | \`songs\` | owner | default — a song in use cannot be deleted at all (spec 018) |`, right after the `POST api/songs/` row
- [X] T031 In `server/core/tests/integration/test_management_access_matrix.py`, add `("PATCH", f"/api/songs/{MISSING_ID}/", "songs", Level.MANAGE)` and `("DELETE", f"/api/songs/{MISSING_ID}/", "songs", Level.OWNER)` to `ENDPOINTS` after the `POST /api/songs/` row. Run the file: Leader must get 403 on the new `DELETE`, and Admin must reach both (404)
- [X] T032 [P] Check whether `specs/songs/tasks.md` lists anything this feature closes (song edit/delete); remove what is now done, and leave the rest untouched
- [X] T033 Run `ruff`, `ruff format` and `python -m mypy .` from `server/`, plus the full suite `pytest` (memory: whole suite at the end of a feature). Then walk through `specs/018-song-edit-delete/quickstart.md`; every row must be covered by a passing test
- [X] T034 Check file sizes and function lengths: `song_service.py`, `views/songs.py`, `dtos.py`, `song_repository.py` and `core/domain/exceptions.py` each stay under 500 lines, and the new functions stay within 4–20 lines

---

## Dependencies & Execution Order

- **Setup (T001)** → **Foundational (T002–T004)** → stories.
- **US1 (T005–T014)** depends only on Foundational.
- **US2 (T015–T019)** depends on Foundational and on T011/T012 (the view class and the route exist).
- **US3 (T020–T028)** depends on US2: it changes `delete_song` in both repository and service.
  US2 and US3 ship together (see the US2 checkpoint).
- **Polish (T029–T034)** last. T029–T031 must land in the same commit as the code.

Inside each story: DTO/exception → repository (protocol + implementation + fake) → service → view/URL → integration tests. Unit tests marked [P] can be written as soon as the unit they test exists.

## Parallel Opportunities

- Foundational: T003 alongside T004.
- US1: T007 (DTO tests) alongside T008/T009. T010 alongside T011/T012 once T009 is done.
- US3: T020 + T021 (exception and its tests) alongside T022 (`SongUsage`). T026 alongside T027.
- Polish: T029, T030 and T032 are independent spec edits.

```text
# US3 example: two independent tracks after T019
Track A: T020 SongInUseError → T021 its wording tests
Track B: T022 SongUsage → T023 get_song_usage → T024 race translation
Join:    T025 service check → T026 / T027 / T028 tests
```

## Implementation Strategy

1. **MVP = US1** (T001–T014): edit only. It is shippable on its own, since `DELETE` is `405`.
2. **Then US2 + US3 as one increment** (T015–T028): never deploy free delete without the in-use guard.
3. **Polish** (T029–T034), then `/ship-dev`.

Commit points that keep mypy green: after T004, T008, T015, T023, T024 (protocol, implementation and fake always together).
