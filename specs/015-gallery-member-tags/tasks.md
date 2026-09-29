---

description: "Task list for Member Tags in Gallery Photos"
---

# Tasks: Member Tags in Gallery Photos

**Input**: Design documents from `specs/015-gallery-member-tags/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md,
contracts/gallery-tags-api.md, quickstart.md

**Tests**: Included. CLAUDE.md §10 requires a test for every new function, and spec FR-044 lists
the regression tests: AND filtering with two members, bulk add/remove keeping other tags, atomic
failure, tags hidden with a trashed photo, the picker exposing only `id` and `name`, Mídia
reaching the picker but not `GET /api/members/`, and the feed reporting a renamed tagged member.
Fakes are named classes in `server/features/gallery/tests/tag_fakes.py` (plus the 013/014 fakes
extended), never inline stubs.

**Organization**: Tasks are grouped by user story (US1–US6 from spec.md). Paths are relative to
the repository root. Run commands from `server/` with `.venv_windows` active (PowerShell).

**Commit rule**: The mypy pre-commit hook checks the whole tree, so every commit must leave it
type-correct. Tasks that must land in the same commit say so. Spec and code go together
(CLAUDE.md §6.2): the Phase 1 docs are committed with the first code commit of Phase 2.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1–US6 from spec.md

---

## Phase 1: Setup

**Purpose**: A known-green baseline, and the specs updated to the target state before any code.

- [X] T001 Run `pytest` and `mypy .` from `server/` on branch `015-gallery-member-tags` and confirm both pass before any change
- [X] T002 Update `specs/gallery/spec.md` to the state this feature produces (spec FR-040):
  - New data model `PhotoTag` (fields, `CASCADE` both sides, unique pair, `tagged_by`/`tagged_at` never serialized, kept while the photo is trashed, removed by the purge).
  - Photo resource gains `members` (last field, `{id, name}` ordered by name then id).
  - Endpoint table gains `PUT /api/photos/{id}/members/`, `POST /api/photos/members/` (limit 200, overlap refused), `GET /api/gallery/taggable-members/` (manage, override), `GET /api/gallery/tagged-members/` (member), and the `member_id` filter (AND) on `GET /api/photos/` and `GET /api/albums/{id}/photos/`.
  - Change Feed section: tag writes, and renames/deletions of tagged members (API and Django admin), make photos changed.
  - Errors table gains `PhotoTagReferenceError` (`404`, `missing_photo_ids`, `missing_member_ids`), the bulk limit, the list overlap and the non-integer `member_id`.
  - Admin: photo page shows tags read-only; tags are not editable in the admin.
  - Add "tags by feature 015" to the header's list of specs.
- [X] T003 [P] Update `specs/gallery/plan.md` (reference D-1…D-13 of `specs/015-gallery-member-tags/plan.md`) and `specs/gallery/tasks.md` (mark "Tagging members in photos" done by feature 015; keep the orphan-listing item)
- [X] T004 [P] Update `specs/accounts/spec.md` (spec FR-041): `Profile.member` (one-to-one, `SET_NULL`, `related_name="profile"`, set only in the Django admin with a name autocomplete, unique), `member_id` read-only in `GET`/`PATCH api/me/profile/`, `is_member` independent of the link
- [X] T005 [P] Update `specs/members/spec.md` (spec FR-042): a member can be tagged in gallery photos and linked to one profile; deleting a member removes its tags and unlinks the profile; a rename or deletion changes the tagged photos in the gallery change feed (API and Django admin, through gallery signal handlers, which do not break rule 3 since they need no editor); `MemberAdmin` has `search_fields = ["name"]`; the picker exception for Mídia (names only)
- [X] T006 [P] Amend `specs/012-feature-role-permissions/spec.md` (spec FR-043):
  - `### gallery` table gains `PUT api/photos/{id}/members/` (manage, default), `POST api/photos/members/` (manage, default), `GET api/gallery/taggable-members/` (manage, override — "names of members for the tag picker").
  - The paragraph below it: `GET api/gallery/tagged-members/` and the `member_id` filter are member endpoints outside the classification.
  - User Story 3 and the `gallery` matrix note: the picker is the one deliberate exception — Mídia reads member **names** through it and nothing else; `GET api/members/`, `api/admin/members/*` and `members/` files stay refused.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Exceptions, pure rules, the tag model and the `members` field every Photo resource
carries. Nothing is written by an endpoint yet.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T007 Move the gallery section of `server/core/domain/exceptions.py` (`AlbumNotFoundError` through `AlbumRestoreNameConflictError`, and `MediaFileTrashedError` stays with the media section) into a new `server/core/domain/gallery_exceptions.py`, and re-export every moved name explicitly from `server/core/domain/exceptions.py` (with `__all__` or `import X as X`) so no import changes anywhere (research R-10). Run `core/tests/unit/test_gallery_exceptions.py` and `test_gallery_trash_exceptions.py` unchanged. First code commit: include T002–T006.
- [X] T008 Add to `server/core/domain/gallery_exceptions.py` and re-export: `PhotoTagReferenceError(NotFoundError)` (`missing_photo_ids`, `missing_member_ids`, both sorted lists; message names them), `TagBulkLimitError(ValidationError)` (`photo_count`, `limit`), `TagListOverlapError(ValidationError)` (`member_ids`); Portuguese messages naming the offending values (research R-10)
- [X] T009 [P] Unit tests for the three exceptions (message, `error_code`, `extra_context`) in `server/core/tests/unit/test_gallery_tag_exceptions.py`
- [X] T010 [P] Add `require_int_list(values: Sequence[object], field: str) -> list[int]` to `server/core/http/parsing.py`: parses each value as `require_int` does, raises `ValidationError` naming the first bad value and the field; with tests in `server/core/tests/unit/test_parsing_guards.py` (ints, strings of ints, `abc`, `1.5`, empty string, empty list)
- [X] T011 [P] Create `server/features/gallery/dtos/tag_dtos.py`: `MemberRef`, `TaggedMember`, `PhotoMembersReplace`, `PhotoTagsBulkChange` (member lists default `[]`), `TagDiff` (`added`, `removed`: `dict[int, list[int]]`; property `changed_photo_ids`) per data-model.md
- [X] T012 Create `server/features/gallery/domain/tag_rules.py`: `TAG_BULK_PHOTO_LIMIT = 200`; `dedupe(ids) -> list[int]` (first-appearance order); `normalise_bulk(change) -> PhotoTagsBulkChange` (dedupe; `ValidationError` for empty `photo_ids` or both member lists empty; `TagListOverlapError`; `TagBulkLimitError`, in that order); `replace_diff(current: set[int], desired: list[int], photo_id) -> TagDiff`; `bulk_diff(current: dict[int, set[int]], add, remove) -> TagDiff` (only real changes) (research R-04)
- [X] T013 [P] Unit tests for every function of `tag_rules.py` in `server/features/gallery/tests/unit/test_tag_rules.py` (duplicates, order of checks, 200 vs 201, no-op add/remove yield an empty diff)
- [X] T014 Create `server/features/gallery/models/tags.py` with `PhotoTag` per data-model.md (`photo` FK `CASCADE` `related_name="tags"`, `member` FK `"members.Member"` `CASCADE` `related_name="+"`, `tagged_by` FK user `SET_NULL` `related_name="+"`, `tagged_at`, constraint `unique_photo_tag`, `Meta.ordering`, `verbose_name`, `__str__` with ids only); import it where the gallery models are collected so Django registers it
- [X] T015 Run `python manage.py makemigrations gallery` to generate `server/features/gallery/migrations/0005_…py` (depends on the latest `members` migration); do not hand-edit it (research R-12)
- [X] T016 [P] Model/migration tests in `server/features/gallery/tests/integration/test_photo_tag_repository.py` and a migration forward/back test (both 015 migrations) in `server/features/gallery/tests/integration/test_member_tag_migrations.py` (unique pair refused; deleting a photo row or a member removes its tags; the table is gone after migrating back to `0004`)
- [X] T017 Add `members: list[MemberRef] = []` (last field) to `PhotoView` in `server/features/gallery/dtos/gallery_dtos.py`; in `server/features/gallery/repositories/gallery_repository.py` add to `_photos()` a `Prefetch("tags", queryset=PhotoTag.objects.select_related("member").order_by("member__name", "member_id"))` and fill `members` in `_to_view` (research R-06)
- [X] T018 Add `MemberRefSerializer` (exactly `id`, `name`) and `members = MemberRefSerializer(many=True)` as the last field of `PhotoSerializer` in `server/features/gallery/serializers/serializers.py`; update its docstring (field added by 015). Same commit as T017.
- [X] T019 [P] Update `server/features/gallery/tests/integration/test_gallery_legacy_reads.py`: every older field keeps its name and meaning, `members` is added last and is `[]` for an untagged photo; and `test_gallery_repository.py`: a tagged photo's view lists members by name then id, in two queries for the whole list (FR-011)

**Checkpoint**: every Photo resource carries `members` (always `[]` so far); tags can only be made in a shell.

---

## Phase 3: User Story 1 — Tag the people in a photo (Priority: P1) 🎯 MVP

**Goal**: A manager reads the picker and replaces a photo's tags; every member sees them.

**Independent Test**: As Mídia, read the picker, `PUT` two members on a photo, read the photo as a
member without a role (both listed by name), replace with one other member (only that one).

### Implementation for User Story 1

- [X] T020 [US1] Add the `NamedMember` Protocol (read-only `id: int`, `name: str` properties), the `MemberDirectory` Protocol (`list_names() -> Sequence[NamedMember]`, `existing_ids(ids: Collection[int]) -> set[int]`) and the `PhotoTagRepository` Protocol (`lock_live_photos`, `current_tags`, `write_diff`, `tagged_members`, `touch_photos_if_renamed`, `touch_photos_of_member`) to `server/features/gallery/repositories/interfaces.py` (data-model.md, Ports)
- [X] T021 [P] [US1] Add `list_names()` (every member, active or not, `order_by("name", "id")`, returning `MemberDTO`) and `existing_ids(ids)` (one `pk__in` query) to `MemberRepositoryImpl` in `server/features/members/repositories/member_repository.py`, and to the `MemberRepository` Protocol in `server/features/members/repositories/interfaces.py`; tests in `server/features/members/tests/integration/test_member_repository.py` (inactive included, order, unknown ids dropped)
- [X] T022 [US1] Create `server/features/gallery/repositories/photo_tag_repository.py` with `PhotoTagRepositoryImpl(clock)`: `lock_live_photos(ids)` (`Photo.objects.select_for_update().filter(pk__in=ids).order_by("id")`, returns found ids), `current_tags(photo_ids)` (one query → `dict[int, set[int]]`), `write_diff(diff, actor_id)` (one `bulk_create(ignore_conflicts=True)` with `tagged_by`/`tagged_at`, one delete of removed pairs, one `update(updated_at=now)` on `diff.changed_photo_ids` only); leave `tagged_members`, `touch_photos_if_renamed`, `touch_photos_of_member` for US2/US5 but define them now if needed for the Protocol (research R-04)
- [X] T023 [P] [US1] Create `server/features/gallery/tests/tag_fakes.py` with `FakeMemberDirectory` and `FakePhotoTagRepository` (in-memory tags, records bumped photo ids, can simulate a member vanishing before `write_diff`)
- [X] T024 [US1] Create `server/features/gallery/services/photo_tag_service.py` with `PhotoTagService(tag_repository, member_directory, gallery_repository)`:
  - `replace_photo_members(photo_id, change: PhotoMembersReplace, actor_id) -> PhotoView`: in `transaction.atomic()`, lock; `PhotoNotFoundError` if the photo is not live; members missing from `existing_ids` → `PhotoTagReferenceError`; `replace_diff`; `write_diff`; `IntegrityError` on write → re-read `existing_ids` and raise `PhotoTagReferenceError` (research R-04); log; return `gallery_repository.get_photo`.
  - `taggable_members() -> list[MemberRef]`.
  - Module-level `_log_tag_change(diff, actor_id)`: event `gallery_tags_changed` with `photo_ids`, `added`, `removed`, `actor_id`; nothing when the diff is empty; ids only (research R-11).
  - Docstrings with intent and one usage example; functions 4–20 lines.
- [X] T025 [P] [US1] Unit tests for `PhotoTagService.replace_photo_members` and `taggable_members` with the named fakes in `server/features/gallery/tests/unit/test_photo_tag_service.py`: replace adds and removes; `[]` clears; repeated ids; unknown photo `404`; trashed photo `404`; unknown members listed in one error, nothing written; FK race mapped to the same error; no-op write bumps nothing and logs nothing; log line has ids only (`caplog`)
- [X] T026 [US1] Create `server/features/gallery/serializers/tag_serializers.py`: `PhotoMembersReplaceSerializer` (`member_ids`: list of integers, required, empty allowed; unknown keys refused like `PhotoUpdateSerializer`) and, for later phases, `PhotoTagsBulkSerializer` and `TaggedMemberSerializer`
- [X] T027 [US1] Create `server/features/gallery/views/tags.py`: `PhotoMembersAPIView` (`PUT`, `GALLERY_WRITE`, `JSONParser`, `require_object_body`, answers `200` Photo resource) and `TaggableMembersAPIView` (`GET`, `[IsAuthenticated, scope_permission(Scope.GALLERY, {"GET": Level.MANAGE})]`, answers via `_not_modified_or_response(request, data, private=True)`) (research R-08)
- [X] T028 [US1] Register `path("api/photos/<int:photo_id>/members/", …)` and `path("api/gallery/taggable-members/", …)` in `server/features/gallery/urls.py`; add `photo_tag_repository` (with `clock`) and `photo_tag_service` (with `member_directory=member_repository`) providers and `"features.gallery.views.tags"` to the wiring list in `server/config/di.py`. Same commit as T027.
- [X] T029 [P] [US1] API tests in `server/features/gallery/tests/integration/test_photo_tags_api.py`: US1 scenarios 1–7 (picker all members incl. inactive, by name; **regression**: picker entries have exactly `{"id", "name"}`; `PUT` two members; member reads the same `members` on both lists; replace; clear; duplicates; inactive member tagged); `Cache-Control: private, no-store` and `304` on the picker
- [X] T030 [P] [US1] Access rows in `server/features/gallery/tests/integration/test_gallery_access.py`: `PUT …/members/` and the picker × {Admin, Liderança, Mídia → allowed; member without role, non-member → `403`, also for an unknown photo id} (US1-8, FR-030)

**Checkpoint**: photos can be tagged one at a time; everyone sees the tags.

---

## Phase 4: User Story 2 — Find the photos someone is in (Priority: P1)

**Goal**: The tagged-member list and the AND filter.

**Independent Test**: P1 tagged A and B, P2 A, P3 B; filter A → P1, P2; A+B → P1; unknown id → `[]`; `abc` → `400`.

### Implementation for User Story 2

- [X] T031 [US2] Add `member_ids: frozenset[int] = frozenset()` to `list_all_photos` and `list_photos_by_album` in the `GalleryRepository` Protocol (`server/features/gallery/repositories/interfaces.py`), in `GalleryRepositoryImpl` (`filter(tags__member_id__in=ids).annotate(matched=Count("tags__member", filter=Q(tags__member_id__in=ids), distinct=True)).filter(matched=len(ids))` only when non-empty, research R-05) and in `FakeGalleryRepository` (`server/features/gallery/tests/fakes.py`). Same commit as T032.
- [X] T032 [US2] Pass `member_ids` through `GalleryService.list_all_photos` and `list_photos_by_album` in `server/features/gallery/services/gallery_service.py`; in `server/features/gallery/views/gallery.py` read `request.query_params.getlist("member_id")`, parse with `require_int_list`, and pass a `frozenset` on both `GET`s
- [X] T033 [US2] Implement `tagged_members()` in `PhotoTagRepositoryImpl` (`PhotoTag.objects.filter(photo__deleted_at__isnull=True).values("member_id", "member__name").annotate(photo_count=Count("photo_id")).order_by("member__name", "member_id")` — the explicit live filter is required, research R-08) and in `FakePhotoTagRepository`; add `PhotoTagService.tagged_members()`
- [X] T034 [US2] Add `TaggedMembersAPIView` (`GET`, `IsMemberUser`, private + ETag) to `server/features/gallery/views/tags.py` and `path("api/gallery/tagged-members/", …)` to `server/features/gallery/urls.py`
- [X] T035 [P] [US2] Unit tests in `server/features/gallery/tests/unit/test_gallery_service.py` (filter passed through) and `test_photo_tag_service.py` (`tagged_members`)
- [X] T036 [P] [US2] Repository tests in `server/features/gallery/tests/integration/test_photo_tag_repository.py`: `tagged_members` counts live photos only and drops a member whose only photos are trashed; filter with one, two, repeated and unknown ids
- [X] T037 [P] [US2] API tests in `server/features/gallery/tests/integration/test_photo_tags_api.py`: **regression** AND filter with two members on `/api/photos/` (P1 only) and on an album (sub-album photo excluded); single member; unknown id `[]`; `abc`, `1.5`, empty value → `400` naming the value; **regression** tags hidden with a trashed photo (filter, tagged-member list, count) and back unchanged after restore; non-member `403` on the tagged-member list (US2 scenarios 1–9)

**Checkpoint**: US1 + US2 = the MVP. Members can find photos by people.

---

## Phase 5: User Story 3 — Photos of me (Priority: P2)

**Goal**: `Profile.member`, set in the Django admin; `member_id` on the profile.

**Independent Test**: Link a profile to A in the admin, read the profile (`member_id` = A), a
second link to A is refused, deleting A leaves `member_id` null.

### Implementation for User Story 3

- [X] T038 [US3] Add `member = models.OneToOneField("members.Member", null=True, blank=True, on_delete=models.SET_NULL, related_name="profile")` to `Profile` in `server/features/accounts/models/profile.py`, with a comment on why it is set only in the admin (research R-02)
- [X] T039 [US3] Run `python manage.py makemigrations accounts` to generate `server/features/accounts/migrations/0005_…py`; do not hand-edit it. Same commit as T038.
- [X] T040 [US3] Add `member_id` to `fields` and `read_only_fields` of `ProfileSerializer` in `server/features/accounts/serializers/serializers.py` (explicit `IntegerField(read_only=True, allow_null=True)`)
- [X] T041 [P] [US3] Register `MemberAdmin` with `search_fields = ["name"]` in `server/features/members/admin.py` (keep the other three models registered as today), and replace `admin.site.register(Profile)` with a `ProfileAdmin` using `autocomplete_fields = ["member"]` in `server/features/accounts/admin.py`
- [X] T042 [P] [US3] Tests in `server/features/accounts/tests/integration/test_profile_member_link.py`: US3 scenarios 1–7 (`member_id` null/set; second link refused by the admin form, nothing saved; the admin autocomplete endpoint finds a member by name; `PATCH` with `member_id` ignored; member deleted → `member_id` null, profile and user kept; `is_member` untouched both ways); migration forward/back with the column removed
- [X] T043 [P] [US3] Update `server/features/accounts/tests/integration/test_profile_api.py` so the full profile shape includes `member_id` and the ETag still changes when the link changes

**Checkpoint**: the app can read its own `member_id` and filter by it.

---

## Phase 6: User Story 4 — Tag many photos at once (Priority: P2)

**Goal**: The bulk endpoint, atomic, keeping other tags.

**Independent Test**: P1 A+B, P2 B; add C and remove B on both → P1 A+C, P2 C.

### Implementation for User Story 4

- [X] T044 [US4] Add `PhotoTagService.change_tags(change: PhotoTagsBulkChange, actor_id) -> list[PhotoView]` in `server/features/gallery/services/photo_tag_service.py`: `normalise_bulk` first (all `400`s before any query); in `transaction.atomic()` lock, collect missing photos and members into one `PhotoTagReferenceError`; `bulk_diff`; `write_diff`; the same `IntegrityError` mapping as T024 (extract a shared private helper, no duplication); log; return views in first-appearance order (research R-13). Keep the file under 500 lines and functions 4–20 lines.
- [X] T045 [US4] Add `PhotoTagsBulkAPIView` (`POST`, `GALLERY_WRITE`, `JSONParser`, `PhotoTagsBulkSerializer` from T026) to `server/features/gallery/views/tags.py` and `path("api/photos/members/", …)` to `server/features/gallery/urls.py`
- [X] T046 [P] [US4] Unit tests in `server/features/gallery/tests/unit/test_photo_tag_service.py`: add/remove on several photos; existing add and missing remove are no-ops; only changed photos bumped; missing ids of both kinds in one error; overlap and limit refused before any repository call (fake records no call)
- [X] T047 [P] [US4] API tests in `server/features/gallery/tests/integration/test_photo_tags_api.py`: **regression** bulk add/remove keeps other tags (US4-1); no-op pairs (US4-2); **regression** atomic failure with an unknown photo, a trashed photo and an unknown member in one request → one `404` listing them, no tag changed (US4-3); 201 photos → `400` with `photo_count`/`limit` (US4-4); overlap → `400` with `member_ids` (US4-5); empty lists → `400`; response order follows `photo_ids`
- [X] T048 [P] [US4] Access rows for `POST /api/photos/members/` in `server/features/gallery/tests/integration/test_gallery_access.py`

**Checkpoint**: event photos can be tagged in one action.

---

## Phase 7: User Story 5 — The app's copy follows the tags (Priority: P2)

**Goal**: The change feed reports photos whose `members` changed, whatever caused it.

**Independent Test**: Cursor; tag P1, rename a member tagged in P2 (in the admin), delete a member
tagged in P3; feed with the cursor returns P1, P2, P3 with their new `members`.

### Implementation for User Story 5

- [X] T049 [US5] Implement `touch_photos_if_renamed(member_id, new_name)` (one `EXISTS` over tags of the member whose `member__name` differs from `new_name`; only then one `update(updated_at=now)` on `Photo.objects.filter(tags__member_id=member_id)`) and `touch_photos_of_member(member_id)` in `PhotoTagRepositoryImpl` (`server/features/gallery/repositories/photo_tag_repository.py`) and `FakePhotoTagRepository` (research R-07)
- [X] T050 [US5] Create `server/features/gallery/signals.py`: module-level injected `_tag_repository()` (like `_album_service` in `features/gallery/admin.py`); `pre_save` handler (skip `raw`, skip when `update_fields` is given without `"name"`, skip new rows without `pk`) calling `touch_photos_if_renamed`; `pre_delete` handler calling `touch_photos_of_member`; a `connect_member_signals()` that connects both with `sender="members.Member"` (string, no import of `features.members`) and fixed `dispatch_uid`s; comment the reasoning and the members-spec rule 3 note (research R-07)
- [X] T051 [US5] Add `ready()` to `GalleryConfig` in `server/features/gallery/apps.py` calling `connect_member_signals()`, and add `"features.gallery.signals"` to the wiring list in `server/config/di.py`. Same commit as T050.
- [X] T052 [P] [US5] Repository tests in `server/features/gallery/tests/integration/test_photo_tag_repository.py`: rename check bumps only when the name changed and only live tagged photos; untagged member → no `UPDATE`; delete bump before cascade
- [X] T053 [P] [US5] Feed API tests in `server/features/gallery/tests/integration/test_change_feed_api.py` with a controlled clock: tag write returns only changed photos (US5-1, FR-028); **regression** rename of a tagged member through `PATCH api/admin/members/{id}/` returns its photos with the new name (US5-2); deletion through `DELETE api/admin/members/{id}/` returns its photos without it (US5-3); the same rename and delete through the Django admin (`Member` change form and the bulk delete action) (US5-4); untagged member renamed, or another field changed → nothing (US5-5, FR-027); a trashed photo is not returned, and its restore returns it with the current name
- [X] T054 [P] [US5] Update `server/features/gallery/tests/integration/test_gallery_legacy_reads.py` (feed Photo resources carry `members`; US5-6)

**Checkpoint**: devices stay in sync with tags, names and deletions.

---

## Phase 8: User Story 6 — The media team sees names, never the roll (Priority: P3)

**Goal**: Pin the 012 separation with the picker exception.

**Independent Test**: As Mídia, picker `200` with `id`/`name` only; `GET /api/members/`,
`api/admin/members/` and a `members/` file refused.

### Implementation for User Story 6

- [X] T055 [US6] Add the three tag routes and the tagged-member list to `server/core/tests/integration/test_management_access_matrix.py` (role × route × method, as for the 014 routes)
- [X] T056 [P] [US6] **Regression** in `server/features/gallery/tests/integration/test_gallery_access.py`: a Mídia user not flagged a member gets `200` on the picker and `403` on `GET /api/members/`; `403` on `api/admin/members/` and on a `members/` file (US6-1–3, FR-031)
- [X] T057 [P] [US6] Assert in `server/features/gallery/tests/integration/test_photo_tags_api.py` that no gallery response carries a member field other than `id`, `name` and (tagged list) `photo_count` (US6-4, FR-035)

**Checkpoint**: the separation of spec 012 holds with its one documented exception.

---

## Phase 9: Polish & Cross-Cutting Concerns

- [X] T058 [P] Add a read-only `tagged_members` method field (names by name then id) to `PhotoAdmin` in `server/features/gallery/admin.py`; do not register `PhotoTag`; tests in `server/features/gallery/tests/integration/test_gallery_admin.py`: the photo page lists the tags with no way to edit them; deleting a tagged member from the member admin succeeds (FR-029, research R-09)
- [X] T059 [P] Extend `server/features/gallery/tests/integration/test_purge_gallery_trash.py`: purging a tagged photo removes its tags; the member keeps its other tags (FR-009)
- [X] T060 [P] Add `server/features/gallery/tests/integration/test_feature_boundaries.py`: no module under `features/gallery` or `features/accounts` (tests excluded) imports `features.members` (constitution; research R-03)
- [X] T061 Run `pytest`, `mypy .`, `ruff check .`, `ruff format --check .` (the project's formatter, per `.pre-commit-config.yaml`) and `bandit -r features core` from `server/`; check every touched file is under 500 lines and every new function 4–20 lines
- [ ] T062 Validate quickstart §3 against a restored production dump (both migrations forward, rollback actually run, forward again; `EXPLAIN` the two-member filter) and walk quickstart §4 on the dev server
- [X] T063 Re-read `specs/gallery/spec.md`, `specs/accounts/spec.md`, `specs/members/spec.md` and spec 012 against the final code; fix any drift in the same commit as the code it describes

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies. T002–T006 are committed with the first code commit
  of Phase 2 (T007).
- **Foundational (Phase 2)**: depends on Setup and blocks every story. Inside it: T007 → T008;
  T011 → T012; T014 → T015; T017 + T018 form one commit (after T011, T014).
- **US1 (Phase 3)**: after Phase 2. T020 → T021/T022/T023 → T024 → T026 → T027 + T028 (one
  commit).
- **US2 (Phase 4)**: after US1 (reuses `PhotoTagRepository`, `views/tags.py` and the tags made by
  `PUT` in its tests). T031 + T032 form one commit.
- **US3 (Phase 5)**: after Phase 1 only (independent of tags); T038 + T039 form one commit. Can run
  in parallel with US1/US2.
- **US4 (Phase 6)**: after US1.
- **US5 (Phase 7)**: after US1 (needs tags to exist); T050 + T051 form one commit.
- **US6 (Phase 8)**: after US1 and US2.
- **Polish (Phase 9)**: after the desired stories.

### Within Each Story

Protocols → implementations and fakes → service → view/URL/DI → tests (unit before
integration). Every commit type-correct.

### Parallel Opportunities

- Phase 1: T003–T006 alongside T002.
- Phase 2: T009, T010, T011, T013, T016, T019 are [P] once their prerequisite lands.
- US1: T021 and T023 alongside T022; tests T025, T029, T030 in parallel once the code is in.
- US3 can be built by another developer in parallel with US1/US2/US4.
- US4 and US5 can run in parallel after US1.

---

## Parallel Example: Foundational

```text
Task: "Add require_int_list to server/core/http/parsing.py"                    (T010)
Task: "Create tag_dtos.py in server/features/gallery/dtos/tag_dtos.py"         (T011)
Task: "Exception unit tests in server/core/tests/unit/test_gallery_tag_exceptions.py" (T009)
```

## Parallel Example: User Story 1 tests

```text
Task: "Service unit tests in server/features/gallery/tests/unit/test_photo_tag_service.py" (T025)
Task: "API tests in server/features/gallery/tests/integration/test_photo_tags_api.py"      (T029)
Task: "Access rows in server/features/gallery/tests/integration/test_gallery_access.py"    (T030)
```

---

## Implementation Strategy

### MVP First (User Stories 1 + 2)

1. Phase 1 + Phase 2: every Photo resource carries `members` (empty).
2. Phase 3 (US1): photos can be tagged; members see who is in them.
3. Phase 4 (US2): the filter and the tagged-member list. **Stop and validate**: this is the
   first shippable slice; the app can already offer "photos of" anyone.

### Incremental Delivery

4. US3: "photos of me" (the app reads `member_id`).
5. US4: bulk tagging for events.
6. US5: the feed follows renames and deletions — ship before the app starts caching tags on
   the device.
7. US6 + Polish: access matrix, admin, boundaries, production-dump validation.

Deploy all of it together (one backend release); the stories are ordered for building, not for
separate deploys.
