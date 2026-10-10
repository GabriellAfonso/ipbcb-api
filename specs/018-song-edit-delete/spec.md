# Feature Specification: Edit and Delete Songs

**Feature Branch**: `018-song-edit-delete`

**Created**: 2026-10-10

**Status**: Draft

## Clarifications

### Session 2026-10-10

- Q: Should the duplicate rule run on every edit, or only when the normalized title + artist pair changes? → A: Only when the normalized pair changes, so legacy duplicates stay editable.
- Q: Does `plays` count play records or distinct dates? → A: Distinct dates; the message says "N domingos".

**Input**: User description: "Add edit and delete endpoints for `Song`, so a worship leader can fix a typo in a song's title, artist or YouTube link, or remove a song registered by mistake, from the Android app. Creating a song already exists (`POST /api/songs/`, see `specs/songs/spec.md`). This feature completes the catalogue's write side with the same rules. Scope: backend only." (full description, including the proposed architecture and test list, in the `/speckit-specify` invocation that created this file)

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Fix a typo in a catalogue song (Priority: P1)

A worship leader notices that a song in the catalogue has a misspelled title, the wrong artist, or a
broken YouTube link. From the Android app they edit just that field and save. The correction shows
up everywhere the song appears (Sunday history, setlists, chord charts, lyrics), because it is the
same catalogue entry, not a new song.

**Why this priority**: typos are the most common catalogue problem and today they can only be fixed
in the Django admin. Every screen that shows the song inherits the mistake until it is fixed.

**Independent Test**: create a song, send a partial edit with only the title, and check that the
response and the song list both show the new title while artist, link and category are unchanged.

**Acceptance Scenarios**:

1. **Given** a song "Ocenas" by "Hillsong", **When** a user with `manage` on `songs` edits the title to "Oceans", **Then** the response is `200` with `{ id, title: "Oceans", artist: "Hillsong", category, youtube_link }` and the song list shows the new title.
2. **Given** a song with a YouTube link, **When** the user sends `youtube_link: ""`, **Then** the link is cleared and title and artist are unchanged.
3. **Given** a song, **When** the user sends only `artist`, **Then** only the artist changes; an omitted field is never cleared.
4. **Given** another song "Oceans" by "Hillsong" already exists, **When** the user edits a different song so it becomes "oceans " by "HILLSONG", **Then** the edit is rejected with `409 CONFLICT` carrying the `title` and `artist` sent, and nothing is saved.
5. **Given** a song "oceans" by "Hillsong", **When** the user changes only the case to "Oceans", **Then** the edit succeeds; a song never conflicts with itself.
6. **Given** a song that has been played on past Sundays, **When** its title is edited, **Then** the Sunday history, top songs and setlists show the new title, and clients holding the old cached version of those lists receive the new content instead of "not modified".

---

### User Story 2 - Delete a song registered by mistake (Priority: P2)

An administrator removes a song that was added to the catalogue by mistake (a test entry, or a
duplicate created before it was noticed) and was never used on a Sunday.

**Why this priority**: less frequent than a typo, and a wrong entry that is never used does little
harm; but without it the catalogue only ever grows.

**Independent Test**: create a song with a chord chart and lyrics, delete it as `owner`, and check
that the song, its chord charts and its lyrics are gone.

**Acceptance Scenarios**:

1. **Given** a song with no plays and on no setlist, **When** a user with `owner` on `songs` deletes it, **Then** the response is `204` with no body, and the song, its chord charts and its lyrics no longer exist.
2. **Given** a user with only `manage` on `songs`, **When** they try to delete a song, **Then** the response is `403` and nothing is deleted.
3. **Given** an id that matches no song, **When** it is deleted, **Then** the response is `404`.

---

### User Story 3 - Understand why a song cannot be deleted (Priority: P2)

An administrator tries to delete a song that is part of the church's Sunday record. The deletion is
refused, and the app explains why in plain language so the administrator knows whether the block is
permanent (the song was played) or will lift on its own (it is only on a setlist that will be purged).

**Why this priority**: it is the safety net of Story 2. Without it, a delete either destroys the
church's history or fails with an unexplained error.

**Independent Test**: register plays for a song and/or put it on a saved setlist, try to delete it,
and check the `409` message and data, and that the song, plays and setlist are untouched.

**Acceptance Scenarios**:

1. **Given** a song played on 7 Sundays and on the setlist of 18/10/2026, **When** an owner deletes it, **Then** the response is `409 CONFLICT` with a pt-BR message such as "A música "Oceans" não pode ser excluída: foi tocada em 7 domingos e está na setlist de 18/10/2026." and data `{ song_id, title, plays: 7, setlist_dates: ["2026-10-18"] }`.
2. **Given** a song with plays but on no setlist, **When** it is deleted, **Then** the `409` message mentions only the plays and `setlist_dates` is empty.
3. **Given** a song on a setlist but never played, **When** it is deleted, **Then** the `409` message mentions only the setlist and `plays` is `0`.
4. **Given** any blocked delete, **Then** the song, its plays, its setlists, its chord charts and its lyrics are all unchanged.
5. **Given** a play is registered for the song between the in-use check and the delete, **When** the delete runs, **Then** the response is still `409` with the same shape, never a server error.

---

### Edge Cases

- Edit body is empty `{}` or contains none of `title`, `artist`, `youtube_link` → `400`.
- Edit body contains any other key (`category`, `id`, …) → `400`, nothing saved, even if valid fields are also present.
- A field sent as `null`, as only whitespace, or longer than its limit after trimming → `400` naming the field, as in create.
- `youtube_link` that is not an http(s) URL → `400`.
- Edit with values identical to the stored ones → `200`, no error.
- Edit that changes only `youtube_link` (or only the case/surrounding whitespace of title or artist) on a song whose pair already repeats another legacy row → `200`. The duplicate rule runs only when the normalized title + artist pair changes (FR-005), so a legacy duplicate can still have its link fixed.
- Unknown id on edit or delete → `404`, for any caller allowed past the permission check.
- Song played more than once on the same date, or the same song twice on one setlist → each date counts once: `plays` counts distinct play dates (FR-014), `setlist_dates` lists each date once, ascending.
- Anonymous caller → `401` on both methods; caller with only `view` on `songs` → `403` on both.

## Requirements *(mandatory)*

### Functional Requirements

**Edit**

- **FR-001**: The system MUST let a caller with `manage` on `songs` partially update a song's `title`, `artist` and `youtube_link` at `PATCH api/songs/{id}/`.
- **FR-002**: Each field MUST follow exactly the same validation as song creation: trimmed; `title` and `artist` 1–100 characters after trimming; `youtube_link` `""` or an http(s) URL of at most 200 characters, stored as sent. The rules MUST be defined once and shared with creation, not re-declared.
- **FR-003**: A field omitted from the body MUST stay unchanged. `youtube_link: ""` MUST clear the link.
- **FR-004**: A body with none of the three fields, or with any other key, MUST be rejected with `400 VALIDATION_ERROR` and save nothing. `category` is never writable.
- **FR-005**: When the edit changes the normalized `title` + `artist` pair (case-insensitive, surrounding whitespace ignored), and a *different* song already has the resulting pair, the edit MUST be rejected with `409 CONFLICT` using the existing duplicate-song error (body carries `title` and `artist`). The song being edited MUST never count as its own duplicate. When the normalized pair is unchanged (link-only edit, case-only change, same values), no duplicate check runs, so legacy duplicate pairs stay editable.
- **FR-006**: The duplicate check MUST be done by the application, not a database constraint; two simultaneous conflicting edits may both succeed (same accepted risk as creation).
- **FR-007**: A successful edit MUST answer `200` with `{ id, title, artist, category, youtube_link }`, the same shape as the song list.

**Delete**

- **FR-008**: The system MUST let a caller with `owner` on `songs` delete a song at `DELETE api/songs/{id}/`, answering `204` with no body.
- **FR-009**: A song referenced by any play record or by any item of a saved setlist MUST NOT be deleted. The system MUST check both before deleting and answer `409 CONFLICT`.
- **FR-010**: The `409` body MUST carry a pt-BR, human-readable `detail` that names the song and states the reason(s), mentioning only the reasons that apply, with dates in `dd/mm/yyyy`; and the data `song_id`, `title`, `plays` (integer, `0` when none) and `setlist_dates` (ISO dates, ascending, distinct, `[]` when none).
- **FR-011**: If a reference appears between the check and the delete, the system MUST still answer the same `409` (with the counts it can determine), never a server error, and MUST delete nothing.
- **FR-012**: Deleting a song MUST remove its chord charts and lyrics with it. They MUST NOT block the delete and are not reported in the response.
- **FR-013**: A delete, allowed or blocked, MUST never modify play records or setlists.
- **FR-014**: `plays` MUST count the distinct dates on which the song has a play record (a song played twice on one date counts once), and the message MUST read "foi tocada em N domingos" ("em 1 domingo" when N is 1). A date that is not a Sunday still counts and is still called "domingo" in the message; this is accepted, since plays are registered for Sunday services.

**Common**

- **FR-015**: Both methods MUST require authentication (`401` otherwise) and the `songs` scope at the default level for the method (`PATCH` `manage`, `DELETE` `owner`), with no override. `GET api/songs/` stays public and `POST api/songs/` is unchanged.
- **FR-016**: An unknown id MUST answer `404 NOT_FOUND` on both methods, using a single-song not-found error distinct from the existing multi-song one (which keeps its `missing_song_ids` meaning).
- **FR-017**: Both endpoints MUST be added to the Endpoint Classification of `specs/012-feature-role-permissions/spec.md` (as `default`, not under Lowered overrides) and to the management access matrix test that mirrors it.
- **FR-018**: After an edit or a delete, every cached read that embeds song data (song list, songs by Sunday, top songs, suggested songs) MUST serve the new content to a client presenting the old cache tag.
- **FR-019**: `specs/songs/spec.md` MUST document both endpoints under `POST /api/songs/`, in the same commit as the code.

### Key Entities

- **Song**: catalogue entry (`title`, `artist`, `youtube_link`, read-only `category`). Edited in place; deleted only when nothing in the Sunday record references it.
- **Play record (`Played`)**: what was played on a date. Permanent history; blocks deletion; never modified here.
- **Setlist item**: a song on a saved Sunday setlist. Blocks deletion until the setlist is purged by its retention window; never modified here.
- **Chord chart / Lyrics**: owned by the song; removed with it.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A leader can correct a song's title, artist or link from the app in a single save, with no admin-panel access.
- **SC-002**: 100% of delete attempts on a song with plays or setlist entries are refused, and 0 play or setlist rows are lost to this feature.
- **SC-003**: Every refused delete returns a message that states which of the two reasons apply, so the user can tell without further lookup whether the block is permanent or temporary.
- **SC-004**: No request to either endpoint results in a server error (5xx) for any combination of body, id, permission level or concurrent play registration covered by the tests.
- **SC-005**: After a song edit, 100% of the cached song-bearing lists return the updated data on the next conditional request.

## Assumptions

- Only the Android app calls these endpoints; it already holds the song's data, so no `GET api/songs/{id}/` is added.
- One leader edits the catalogue at a time, so the duplicate-check race is accepted, as in creation.
- `null` for a field is treated as invalid (`400`), not as "clear"; clearing is only defined for `youtube_link`, via `""`.
- The `409` `detail` is pt-BR because the app shows it to the user (project rule: user-facing content may be in Portuguese). This diverges from the precedent `ServiceInUseError`, whose message is English.
- Cached reads derive their cache tag from the response body, so edits and deletes invalidate them with no extra work; this is confirmed for all four reads during planning.
- No model change and no migration.

## Out of Scope

- Writing `category`.
- `GET api/songs/{id}/`.
- Editing or deleting plays or setlist rows (covered by their own endpoints).
- Merging duplicate songs (moving plays from one song to another).
- Soft delete / archive.
- The Android app side (separate spec).
