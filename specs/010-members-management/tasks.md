---

description: "Task list for Members Management for Church Leaders"
---

# Tasks: Members Management for Church Leaders

**Input**: Design documents from `specs/010-members-management/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/admin-members-api.md,
quickstart.md

**Tests**: Included. CLAUDE.md §10 requires a test for every new function; fakes are named
classes in `server/features/members/tests/fakes.py`.

**Organization**: Tasks are grouped by user story. All paths are relative to the repository
root. Run commands from `server/` with `.venv_windows` active.

**Commit rule**: the mypy pre-commit hook checks the whole tree, so every commit must leave it
type-correct. A Protocol method and its implementation (and its fake) land in the same commit.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1–US5 from spec.md

---

## Phase 1: Setup

**Purpose**: Package skeleton for the new modules.

- [X] T001 Create empty packages `server/features/members/domain/__init__.py` and confirm `server/features/members/tests/unit/__init__.py`, `server/features/members/tests/integration/__init__.py` exist; create `server/features/members/tests/fakes.py` with a module docstring only

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Schema, shared DTOs, domain rules, history write path and photo storage used by
more than one story.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

### Exception

- [X] T002 [P] Add `MemberNotFoundError(NotFoundError)` to `server/core/domain/exceptions.py`, message `f"Membro não encontrado: {member_id}."` taking `member_id: int` (pattern: `ProfileNotFoundError`)
- [X] T003 [P] Test in `server/core/tests/unit/test_exception_handler.py`: `MemberNotFoundError(7)` maps to 404, `error_code` `NOT_FOUND`, `detail` contains `7`

### Model and migration

- [X] T004 Edit `server/features/members/models/member.py`: add comment above `is_active` stating it means "valid profile" and that only valid profiles appear in the regular list and birthdays; add `photo = models.ImageField(upload_to="members/", null=True, blank=True)` with a comment pointing to `specs/members/spec.md` (leader-only, separate from `Profile.photo`, written through `MemberPhotoStorage`)
- [X] T005 Create `server/features/members/models/member_change_log.py` with `MemberChangeLog` per data-model.md (`member` FK CASCADE `related_name="change_log"`, `editor` FK `settings.AUTH_USER_MODEL` SET_NULL null `related_name="+"`, `field` CharField 32, `old_value`/`new_value` TextField null, `changed_at` auto_now_add; `Meta.ordering = ["-changed_at", "-id"]`, `verbose_name`, `verbose_name_plural`; `__str__` without member data); export it from `server/features/members/models/__init__.py`
- [X] T006 Run `python manage.py makemigrations members` to generate `server/features/members/migrations/0003_*.py` (AddField `photo`, CreateModel `MemberChangeLog`); do not hand-edit; verify `migrate` then `migrate members 0002` then `migrate` round-trips on the local DB
- [X] T007 [P] Tests in `server/features/members/tests/unit/test_models.py`: `MemberChangeLog.__str__` has no member name; default ordering newest first; deleting a member deletes its entries; deleting the editor user keeps entries with `editor=None` (mark `django_db`)

### DTOs

- [X] T008 Add to `server/features/members/dtos.py`: `NamedRefDTO`, `MemberSummaryDTO`, `MemberRecordDTO`, `MemberFieldChange`, `ChangeLogEditorDTO`, `ChangeLogEntryDTO`, `MemberOptionsDTO`, `MemberCreateDTO(StrictBaseModel)`, `MemberPatchDTO(StrictBaseModel)` exactly as in data-model.md (`StrictBaseModel` from `core.application.dtos.strict_base`); keep `MemberDTO`, `BirthdayDTO` unchanged

### Domain rules (pure)

- [X] T009 [P] Tests first in `server/features/members/tests/unit/test_member_changes.py`: `render_history_value` for str, blank str → None, None, date → ISO, bool → "true"/"false", NamedRefDTO → name, list of NamedRefDTO → sorted names joined ", ", empty list → None; `diff_member_records` returns one change per differing field, none for equal records, one `ministries` change for `A, B` → `A, C`, and ignores order of ministries
- [X] T010 [P] Tests first in `server/features/members/tests/unit/test_member_dates.py`: future birth date rejected, future baptism date rejected, baptism before birth rejected, equal dates accepted, missing either date accepted; each error message contains the offending date(s)
- [X] T011 Implement `server/features/members/domain/member_changes.py`: `HISTORY_FIELDS` tuple (the 10 editable field keys from data-model.md), `CREATED_FIELD = "created"`, `PHOTO_FIELD = "photo"`, `PHOTO_CHANGED = "photo changed"`, `PHOTO_REMOVED = "photo removed"`, `render_history_value(value) -> str | None`, `diff_member_records(before: MemberRecordDTO, after: MemberRecordDTO) -> list[MemberFieldChange]` (research R-02); docstrings with one usage example
- [X] T012 Implement `server/features/members/domain/member_dates.py`: `validate_member_dates(birth_date, baptism_date, today) -> None` raising `core.domain.exceptions.ValidationError` with Portuguese messages naming the dates (research R-04)

### History write path

- [X] T013 Add `MemberChangeLogRepository` Protocol to `server/features/members/repositories/interfaces.py` with `add_entries(member_id: int, editor_id: UUID | None, changes: list[MemberFieldChange]) -> None`
- [X] T014 Implement `MemberChangeLogRepositoryImpl.add_entries` in `server/features/members/repositories/member_change_log_repository.py` with one `bulk_create`
- [X] T015 Add `FakeMemberChangeLogRepository` (records `(member_id, editor_id, changes)` calls) to `server/features/members/tests/fakes.py`
- [X] T016 [P] Integration test in `server/features/members/tests/integration/test_member_change_log_repository.py`: `add_entries` writes all rows in one query (`django_assert_num_queries(1)`), empty list writes nothing

### Photo storage

- [X] T017 Add `MemberPhotoStorage` Protocol to `server/features/members/repositories/interfaces.py`: `save(extension: str, upload: IO[bytes]) -> str`, `delete(name: str) -> None`
- [X] T018 Implement `DefaultStorageMemberPhotoStorage` in `server/features/members/repositories/member_photo_storage.py` over `default_storage`: `save` writes `members/{uuid4().hex}.{extension}` via `File(upload)` (streamed) and returns the stored name; `delete` ignores a missing file; docstring explains no member name in the path and cites spec 009
- [X] T019 Add `FakeMemberPhotoStorage` (in-memory dict, `fail_on_save` flag, records deletions) to `server/features/members/tests/fakes.py`
- [X] T020 [P] Integration test in `server/features/members/tests/integration/test_member_photo_storage.py` with `override_settings(MEDIA_ROOT=tmp_path)`: saved name matches `^members/[0-9a-f]{32}\.png$`, file exists, `delete` removes it, `delete` of a missing name does not raise

### Roster repository skeleton and DI

- [X] T021 Add `MemberRosterRepository` Protocol to `server/features/members/repositories/interfaces.py` with `exists(member_id: int) -> bool`, and `MemberRosterRepositoryImpl` in `server/features/members/repositories/member_roster_repository.py` implementing it; add `FakeMemberRosterRepository` (backed by a dict of `MemberRecordDTO`) to `server/features/members/tests/fakes.py`
- [X] T022 Add `FixedClock` to `server/features/members/tests/fakes.py`
- [X] T023 Register `member_roster_repository`, `member_change_log_repository`, `member_photo_storage` providers in `server/config/di.py` (Factory)

**Checkpoint**: migration applied, domain rules green, ports in place.

---

## Phase 3: User Story 1 - Leader browses and opens member records (Priority: P1) 🎯 MVP

**Goal**: `GET api/admin/members/` and `GET api/admin/members/{id}/` for leaders only.

**Independent Test**: Seed valid and not-valid members; leader gets all of them and a full
record; plain member and anonymous are refused; 304 on unchanged data with private headers.

### Tests for User Story 1

- [X] T024 [P] [US1] Service tests in `server/features/members/tests/unit/test_member_roster_service.py`: `list_members` returns what the fake holds; `get_member` raises `MemberNotFoundError` for an unknown id
- [X] T025 [P] [US1] Repository tests in `server/features/members/tests/integration/test_member_roster_repository.py`: `list_members` includes `is_active=False`, ordered by name, constant query count for 1 vs 20 members; `get_record` returns ministries sorted by name, status/role as NamedRefDTO or None, `photo_path` None without photo; `get_record` of unknown id returns None; query count ≤ 3
- [X] T026 [P] [US1] API tests in `server/features/members/tests/integration/test_admin_members_api.py` (list + detail): 401 anonymous, 403 plain member (`make_member_client`), 403 user without profile, 200 leader (`make_admin_client`) with exactly the fields in contracts/admin-members-api.md, not-valid member included, 404 unknown id with `NOT_FOUND`, `photo_url` absolute when a photo exists and null otherwise, `Cache-Control: private, no-store` + `Vary: Authorization`, second request with `If-None-Match` → 304

### Implementation for User Story 1

- [X] T027 [US1] Add `list_members() -> list[MemberSummaryDTO]` and `get_record(member_id: int) -> MemberRecordDTO | None` to `MemberRosterRepository` Protocol, `MemberRosterRepositoryImpl` (`select_related("status", "role")`, `prefetch_related` ministries ordered by name, `photo_path` from `member.photo.url` when set) and `FakeMemberRosterRepository`
- [X] T028 [US1] Create `server/features/members/services/member_roster_service.py` with `MemberRosterService(roster_repository, change_log_repository, photo_storage, clock)`, methods `list_members()` and `get_member(member_id)` (raises `MemberNotFoundError`); register `member_roster_service` in `server/config/di.py` with `clock=clock`
- [X] T029 [US1] Create `server/features/members/serializers/admin_member_serializers.py` with output serializers `NamedRefSerializer`, `MemberSummarySerializer`, `MemberRecordSerializer` (explicit `fields`, never `"__all__"`; `photo_url` built from `photo_path` with `request.build_absolute_uri`)
- [X] T030 [US1] Create `server/features/members/views/admin_members.py` with `AdminMemberListAPIView.get` and `AdminMemberDetailAPIView.get`, `permission_classes = [IsAuthenticated, IsAdminUser]`, responses via `_not_modified_or_response(request, body, private=True)`; list body `{"members": [...]}`
- [X] T031 [US1] Add routes `api/admin/members/` and `api/admin/members/<int:member_id>/` to `server/features/members/urls.py`; add `"features.members.views.admin_members"` to the wiring list in `server/config/di.py`

**Checkpoint**: US1 tests green; leaders can read the roll.

---

## Phase 4: User Story 2 - Leader creates and edits a member (Priority: P1)

**Goal**: `GET options/`, `POST` create with `created` history row, `PATCH` with one history
row per changed field, all in one transaction.

**Independent Test**: Fetch options, create with them, patch a subset, read the record back;
check validation errors store nothing.

### Tests for User Story 2

- [X] T032 [P] [US2] Service tests in `server/features/members/tests/unit/test_member_roster_service.py` (`django_db`, fakes): `get_options`; `create_member` writes one `created` change with the editor id; unknown status/role id → `ValidationError` naming the id; unknown ministry ids → error listing them; future date → error; `update_member` writes one change per changed field, none for unchanged fields, one ministries change, `status_id=None` clears status; nothing written to the change-log fake when validation fails; baptism-before-birth checked against the merged record (patch only `baptism_date`); unknown member → `MemberNotFoundError`; log records `member_created`/`member_updated` carry only `member_id`, `editor_id`, `changed_fields` (use `caplog`)
- [X] T033 [P] [US2] Repository tests in `server/features/members/tests/integration/test_member_roster_repository.py`: `get_options` ordered by name; `find_status`/`find_role` None for unknown id; `find_ministries` returns only existing ids in one query; `create` and `update` persist fields and replace ministries
- [X] T034 [P] [US2] API tests in `server/features/members/tests/integration/test_admin_members_api.py` (options, POST, PATCH): 403 for plain member on each; options shape; POST 201 with record, 400 on blank name, invalid gender, non-int id, unknown key (`photo`, `id`, `created_at`), non-object body (JSON array); PATCH 200 partial update, empty body 200 with no history, 400 leaves record and history unchanged (atomicity), unchanged regular list after marking `is_active=false` → member absent from `/api/members/` and birthdays but present in the leader list

### Implementation for User Story 2

- [X] T035 [US2] Add to `MemberRosterRepository` Protocol, `MemberRosterRepositoryImpl` and `FakeMemberRosterRepository`: `get_options() -> MemberOptionsDTO`, `find_status(id) -> NamedRefDTO | None`, `find_role(id) -> NamedRefDTO | None`, `find_ministries(ids: list[int]) -> list[NamedRefDTO]`, `create(dto: MemberCreateDTO) -> int`, `update(member_id: int, dto: MemberPatchDTO) -> None` applying only `dto.model_fields_set` (`status_id`/`role_id` to the FK `_id` columns, `ministry_ids` with `.set(ids)`)
- [X] T036 [US2] Implement in `MemberRosterService` (`server/features/members/services/member_roster_service.py`): `get_options()`, `create_member(dto, editor_id)`, `update_member(member_id, dto, editor_id)` per research R-01–R-04 and R-09 — reference validation via repository lookups, `validate_member_dates` with `clock.now().date()`, `transaction.atomic()` around write + `change_log_repository.add_entries`, snapshot diff with `diff_member_records`; each method ≤ 20 lines, extract helpers
- [X] T037 [US2] Add input serializers `MemberCreateSerializer` and `MemberPatchSerializer` to `server/features/members/serializers/admin_member_serializers.py`: explicit fields (`name`, `first_name`, `last_name`, `birth_date`, `gender`, `status_id`, `role_id`, `ministry_ids`, `baptism_date`, `is_active`), `name` required/non-blank/≤255 on create and non-null/non-blank on patch, `gender` ChoiceField `M`/`F` nullable, reject unknown keys in `validate` (`to_internal_value` check against `initial_data`)
- [X] T038 [US2] Add `AdminMemberListAPIView.post` and `AdminMemberDetailAPIView.patch` to `server/features/members/views/admin_members.py`: `require_object_body(request.data)`, serializer → `MemberCreateDTO`/`MemberPatchDTO` (only keys present, so `model_fields_set` is right), service call with `request.user.pk`, respond 201/200 with `MemberRecordSerializer`; add `AdminMemberOptionsAPIView.get` (private cache)
- [X] T039 [US2] Add route `api/admin/members/options/` to `server/features/members/urls.py` (before the `<int:member_id>/` route for readability)

**Checkpoint**: US1 + US2 green; leaders can keep the roll current.

---

## Phase 5: User Story 3 - Leader reads the edit history (Priority: P2)

**Goal**: `GET api/admin/members/{id}/history/`, newest first, with editor name.

**Independent Test**: Create, edit two fields, change ministries, read history; delete the
editor account and read again.

### Tests for User Story 3

- [X] T040 [P] [US3] Service tests in `server/features/members/tests/unit/test_member_change_log_service.py`: returns entries from the fake; unknown member → `MemberNotFoundError`
- [X] T041 [P] [US3] Repository tests in `server/features/members/tests/integration/test_member_change_log_repository.py`: `list_for_member` newest first (ties by id desc), editor name from profile name, username when profile name is blank, `editor=None` after the user is deleted, one query for 10 entries
- [X] T042 [P] [US3] API tests in `server/features/members/tests/integration/test_admin_member_history_api.py`: 401/403/404; after create + PATCH of two fields → `created` + 2 rows with old/new values as in the contract; ministries row `"A, B"` → `"A, C"`; reading the record or history adds no rows; private cache headers + 304

### Implementation for User Story 3

- [X] T043 [US3] Add `list_for_member(member_id: int) -> list[ChangeLogEntryDTO]` to `MemberChangeLogRepository` Protocol, `MemberChangeLogRepositoryImpl` (`select_related("editor__profile")`, research R-07) and `FakeMemberChangeLogRepository`
- [X] T044 [US3] Create `server/features/members/services/member_change_log_service.py` with `MemberChangeLogService(change_log_repository, roster_repository).list_history(member_id)` (404 via `roster_repository.exists`); register in `server/config/di.py`
- [X] T045 [US3] Add `ChangeLogEntrySerializer` to `server/features/members/serializers/admin_member_serializers.py`; create `server/features/members/views/admin_member_history.py` with `AdminMemberHistoryAPIView.get` (`[IsAuthenticated, IsAdminUser]`, body `{"history": [...]}`, private cache); route `api/admin/members/<int:member_id>/history/` in `server/features/members/urls.py`; wire the module in `server/config/di.py`

**Checkpoint**: history readable.

---

## Phase 6: User Story 4 - Leader manages the member photo (Priority: P2)

**Goal**: `PUT` / `DELETE api/admin/members/{id}/photo/`, leader-only reads via the media route.

**Independent Test**: Upload, fetch as leader and member, replace, remove; check disk and
history after each step.

### Tests for User Story 4

- [X] T046 [P] [US4] Service tests in `server/features/members/tests/unit/test_member_photo_service.py` (`django_db`, fakes, `django_capture_on_commit_callbacks`): invalid image → `ValidationError`, storage and repository untouched; replace with an old photo → new saved, row updated, one `photo`/`photo changed` change, old deleted only in the on-commit callback; history write failure → new file deleted, row unchanged, old not deleted; remove with photo → `photo removed` change and on-commit delete; remove without photo → no change, no delete; unknown member → `MemberNotFoundError`; log records carry only allowed keys
- [X] T047 [P] [US4] API tests in `server/features/members/tests/integration/test_admin_member_photo_api.py` with `override_settings(MEDIA_ROOT=tmp_path, DEBUG=False)` and `captureOnCommitCallbacks(execute=True)`: 401/403/404; PUT without `photo` → 400; PUT text file named `.png` → 400 and existing photo intact; PUT JPEG → 200 `photo_url` matching `members/<hex>.jpg`; replace removes old file from disk; `photo_url` via the media route → 200 (X-Accel-Redirect) for leader, 403 for plain member; DELETE → 204, file gone, history row; DELETE again → 204, no new row

### Implementation for User Story 4

- [X] T048 [US4] Add `get_photo_name(member_id) -> str | None` and `set_photo_name(member_id, name: str | None) -> None` to `MemberRosterRepository` Protocol, `MemberRosterRepositoryImpl` (`update(photo=...)`, no file write) and `FakeMemberRosterRepository`
- [X] T049 [US4] Create `server/features/members/services/member_photo_service.py` with `MemberPhotoService(roster_repository, change_log_repository, photo_storage)`: `replace_photo(member_id, upload, editor_id) -> str` and `remove_photo(member_id, editor_id) -> None` following research R-05 exactly (`detect_image_extension` first; save outside the transaction; `transaction.on_commit(..., robust=True)` for the old file; delete the new file and re-raise on failure); return the photo URL path; register in `server/config/di.py`
- [X] T050 [US4] Create `server/features/members/views/admin_member_photo.py` with `AdminMemberPhotoAPIView` (`[IsAuthenticated, IsAdminUser]`, `parser_classes = [MultiPartParser, FormParser]`): `put` (400 domain `ValidationError` when `photo` is missing, 200 `{"photo_url": ...}`), `delete` (204); route `api/admin/members/<int:member_id>/photo/` in `server/features/members/urls.py`; wire the module in `server/config/di.py`

**Checkpoint**: photo flow complete; `members/` served only to leaders.

---

## Phase 7: User Story 5 - Leader deletes a member (Priority: P3)

**Goal**: `DELETE api/admin/members/{id}/` removes record, history and photo file.

**Independent Test**: Member with photo and history → delete → row, rows and file gone.

### Tests for User Story 5

- [X] T051 [P] [US5] Service tests in `server/features/members/tests/unit/test_member_roster_service.py`: `delete_member` removes via repository, schedules photo deletion on commit only when a photo exists, logs `member_deleted` with only allowed keys; unknown id → `MemberNotFoundError`
- [X] T052 [P] [US5] API tests in `server/features/members/tests/integration/test_admin_members_api.py`: 403 plain member; 204 leader; member, its `MemberChangeLog` rows and photo file are gone; 404 on second delete

### Implementation for User Story 5

- [X] T053 [US5] Add `delete(member_id) -> None` to `MemberRosterRepository` Protocol, `MemberRosterRepositoryImpl` and `FakeMemberRosterRepository`
- [X] T054 [US5] Implement `MemberRosterService.delete_member(member_id, editor_id)` in `server/features/members/services/member_roster_service.py`: read photo name, `transaction.atomic()` delete, `on_commit(photo_storage.delete, robust=True)` when a photo existed
- [X] T055 [US5] Add `AdminMemberDetailAPIView.delete` (204) to `server/features/members/views/admin_members.py`

**Checkpoint**: all stories functional.

---

## Phase 8: Polish & Cross-Cutting Concerns

- [X] T056 [P] Regression tests in `server/features/members/tests/integration/test_members_api.py` and `test_birthdays_api.py`: regular list still returns only `id`, `name`, only `is_active=True`; birthdays unchanged for a not-valid member; a leader-only `photo` on a member does not appear in either response
- [X] T057 [P] Log-hygiene test in `server/features/members/tests/integration/test_admin_members_api.py`: across create, patch, photo replace, delete, no captured log record contains the member's name, birth date or photo path (SC-006)
- [X] T058 Update `specs/members/spec.md`: remove the **[010]** markers for what shipped; add the Django admin limitation (R-12 default: admin edits/deletes write no history and a delete there leaves the photo file) under Business Rules
- [X] T059 Run the full quickstart §1 (`pytest`, `mypy`, `pre-commit run --all-files`, `makemigrations --check --dry-run`) and fix findings
- [ ] T060 Run quickstart §2–§3 manually against a local server and record the outcome in the PR description

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (1)** → **Foundational (2)** → user stories.
- **US1 (3)**: after Foundational. MVP.
- **US2 (4)**: after US1 (reuses `MemberRosterService`, `admin_members.py`, record serializer).
- **US3 (5)**: after Foundational; reads rows US2 writes, so its API test needs US2 — service
  and repository tasks can run in parallel with US2.
- **US4 (6)**: after Foundational + T027 (record `photo_path`); independent of US2/US3 except
  its history assertions reuse `MemberChangeLogRepository`.
- **US5 (7)**: after US1 (same view file) and Foundational photo storage.
- **Polish (8)**: after all stories.

### Within Each Story

Tests first (they fail), then Protocol + implementation + fake in one step (mypy), then
service, then serializer/view/URL/DI.

### Parallel Opportunities

- Foundational: T002/T003, T007, T009/T010, T016, T020 in parallel once their targets exist.
- Each story's test tasks marked [P] run in parallel (different files).
- US3 and US4 can be developed in parallel after US1.

## Parallel Example: User Story 1

```text
T024 [US1] service tests       — tests/unit/test_member_roster_service.py
T025 [US1] repository tests    — tests/integration/test_member_roster_repository.py
T026 [US1] API tests           — tests/integration/test_admin_members_api.py
```

## Parallel Example: User Story 4

```text
T046 [US4] service tests       — tests/unit/test_member_photo_service.py
T047 [US4] API tests           — tests/integration/test_admin_member_photo_api.py
```

## Implementation Strategy

### MVP First

1. Phases 1–2.
2. Phase 3 (US1): leaders read the whole roll. Stop and validate with quickstart steps 1 and 13.

### Incremental Delivery

1. + US2 → roll editable (the screen's main purpose).
2. + US3 → history visible.
3. + US4 → photos.
4. + US5 → delete.
5. Polish.

Each step is a coherent commit set; spec and code go together (CLAUDE.md §6.2).
