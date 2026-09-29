# Implementation Plan: Member Tags in Gallery Photos

**Branch**: `015-gallery-member-tags` | **Date**: 2026-09-29 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/015-gallery-member-tags/spec.md`

## Summary

Managers tag members in photos, every member sees who is in a photo and filters the gallery by
people (AND), and a profile can be linked by hand to its member record so the app can offer
"photos of me".

A new `PhotoTag` model in `features/gallery` pairs a photo with a `"members.Member"` (string
reference, `CASCADE` on both sides, unique pair, audit fields). `Profile` gains a nullable
one-to-one `member` (`SET_NULL`), edited only in the Django admin through a name autocomplete;
the profile resource gains read-only `member_id`. The Photo resource gains `members` (`{id,
name}`, by name), prefetched in the one repository helper every Photo resource goes through.
`PhotoTagService` handles the two writes atomically: normalise and check in pure domain code, lock
the live photo rows, collect every missing id into one `404`, write the diff, bump `updated_at` on
the changed photos only, log one line. The picker reads the roll through a `MemberDirectory` port
that `features/members` implements and `config/di.py` wires; the tagged-member list and the names
on photos come through the `PhotoTag.member` relation. The filter is one `COUNT(DISTINCT)` join.
Renames and deletions of tagged members reach the change feed through gallery signal handlers
connected to `"members.Member"` by string, so the API and the Django admin are both covered. The
gallery exceptions move to `core/domain/gallery_exceptions.py`, re-exported, to keep
`exceptions.py` under 500 lines.

## Technical Context

**Language/Version**: Python 3.14, `.venv_windows`

**Primary Dependencies**: Django 6.0, DRF 3.17, dependency-injector, Pydantic 2.12. No new
dependency.

**Storage**: PostgreSQL in production, SQLite in tests. Two generated migrations,
`gallery/0005` and `accounts/0005` (R-12). No data migration.

**Testing**: pytest + pytest-django; named fakes in `features/gallery/tests/tag_fakes.py`
(`FakePhotoTagRepository`, `FakeMemberDirectory`) plus the 013/014 fakes extended for
`PhotoView.members` and the filter; mypy, ruff, bandit.

**Target Platform**: Linux container behind nginx, prefix `/ipbcb/`.

**Project Type**: Web service (REST API), single Android client.

**Performance Goals**: photo lists +1 query for all tags (prefetch), whatever their size; filter:
one extra join and a grouped count; tag writes: lock + read tags + one insert + one delete + one
`UPDATE`, no per-row queries; a `Member` save costs one indexed `EXISTS` (plus one `UPDATE` only
when a tagged member was renamed).

**Constraints**: features never import each other (gallery ↔ members through a string FK, a port
and lazy-sender signals; accounts ↔ members through a string FK); services never see HTTP; ORM only
in repositories; existing responses only gain `members` / `member_id`; migrations 0001–0004
untouched; every file under 500 lines.

**Scale/Scope**: a few hundred members, low thousands of photos, a handful of tags per photo;
4 new endpoint-methods, 2 existing reads gain a filter, 2 resources gain a field.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design; result unchanged.*

| Rule (`specs/constitution.md`, `CLAUDE.md`) | Status |
|---|---|
| `IsAuthenticated` on every authenticated view; one scope per management endpoint | ✅ tag writes `GALLERY_WRITE`; picker `[IsAuthenticated, scope_permission(Scope.GALLERY, {"GET": Level.MANAGE})]`; tagged-member list `IsMemberUser` |
| Overrides only raise the level | ✅ picker `GET` → `manage`, checked by `validate_overrides` at import |
| Features never import each other | ✅ `"members.Member"` by string (precedent `features/schedule`); `MemberDirectory` Protocol in gallery, implemented structurally in members, wired in `config/di.py` (R-03); signals with `sender="members.Member"` (R-07) |
| Views → services → repositories; ORM only in repositories | ✅ `PhotoTagRepositoryImpl`; signal handlers are entry points that call the repository, like views |
| Services never import HTTP objects | ✅ services take ids and the actor UUID; `member_id` parsed in the view |
| DI via `config/di.py`; injection, not globals | ✅ new providers; `Clock` into the tag repository; handlers injected at module level |
| DTOs are Pydantic | ✅ `MemberRef`, `TaggedMember`, `PhotoMembersReplace`, `PhotoTagsBulkChange`, `TagDiff` |
| Input validated; no raw `int()` on request fields | ✅ serializers for bodies; `require_int_list` for the query parameter |
| No queries in loops | ✅ prefetch for `members`; bulk insert/delete/update; one directory query for existence |
| Error shape canonical; domain exceptions with offending values | ✅ 3 new exceptions with `extra_context` (R-10) |
| Sensitive data (members domain) | ✅ explicit serializer fields (`id`, `name` only); ids only in logs; picker and tagged list `private, no-store` (R-08, FR-033/034) |
| Caching of user-dependent bodies | ✅ profile keeps `private=True`; the two member lists are declared private as defence in depth |
| Structured JSON logs, ids only | ✅ R-11 |
| Models have `__str__`, `Meta.ordering`, `Meta.verbose_name` | ✅ `PhotoTag` (ids only in `__str__`) |
| Migrations generated; data migrations with reason; applied ones untouched | ✅ two generated, no data migration; production dump + real rollback (quickstart §3) |
| Spec before code; spec and code in the same commit | ✅ step 0 |
| Functions 4–20 lines, files < 500 lines | ✅ exceptions split (R-10); service split below |

**Deviations recorded, decided with the requester (2026-09-29)**:

- **Signals** (R-07). `specs/members/spec.md` rule 3 says "No signals" — for the change history,
  because a signal does not know the editor. The gallery's handlers need no editor and are the
  only hook the Django admin paths share with the API; the members rule stays as it is.
- **Exceptions module split** (R-10): `core/domain/exceptions.py` keeps being the import path
  for every domain exception, as CLAUDE.md §2 requires, by re-exporting.

**Amendments to prior specs (not violations)**: spec 012 User Story 3 gains the picker exception
(FR-031); spec 014's feed rule gains the `members` field; members and accounts domain specs gain
the link and tags. All listed in spec FR-040–FR-043 and done in step 0.

Gate: **pass**.

## Technical Decisions

Full reasoning in [research.md](research.md).

- **D-1** `PhotoTag` in gallery, string FK to members, `CASCADE` both sides, unique pair,
  `tagged_by` / `tagged_at` (R-01).
- **D-2** `Profile.member` one-to-one `SET_NULL`, `related_name="profile"`; admin autocomplete;
  read-only `member_id` (R-02).
- **D-3** Names through the relation; the roll (picker, existence) through the `MemberDirectory`
  port (R-03).
- **D-4** Tag writes: pure normalise/diff, photo row locks by id, one `404` listing every missing
  photo (unknown or trashed) and member, FK race mapped to it, bump only changed photos (R-04).
- **D-5** AND filter via `COUNT(DISTINCT)` on one join; `require_int_list` (R-05).
- **D-6** `PhotoView.members` via one prefetch in `_photos()`; `members` last in the serializer
  (R-06).
- **D-7** Feed: tag writes bump; member rename/delete via gallery signals on
  `"members.Member"` (R-07).
- **D-8** Picker from the directory; tagged list from `PhotoTag` with an explicit live-photo
  filter; both private with ETag (R-08).
- **D-9** Tags read-only on the photo admin page; `PhotoTag` not registered (R-09).
- **D-10** Gallery exceptions moved to `core/domain/gallery_exceptions.py`, re-exported; 3 new
  ones (R-10).
- **D-11** One log line per changing write, ids only (R-11).
- **D-12** Two generated migrations (R-12).
- **D-13** Response orders (R-13).

## Spec adjustments made while planning

Recorded in the spec's Clarifications, same commit:

- FR-015 / Assumptions: the atomic-failure error is `404` `NOT_FOUND` with `missing_photo_ids`
  (unknown **and** trashed photos, merged, as 014 merges them) and `missing_member_ids`. A caller
  with `manage` does not learn which ids are in the trash (R-04).

## Service split

| Service | Responsibility | Depends on |
|---------|----------------|------------|
| `PhotoTagService` (new) | `replace_photo_members`, `change_tags`, `taggable_members`, `tagged_members` | `PhotoTagRepository`, `MemberDirectory`, `GalleryRepository` (views of the result) |
| `GalleryService` *(013)* | + `member_ids` on `list_all_photos` / `list_photos_by_album` | unchanged |
| `GalleryChangeFeedService` *(014)* | unchanged: tag, rename and delete changes arrive as `updated_at` | unchanged |
| `ProfileService` *(accounts)* | unchanged: `member_id` is a serializer field of the profile row | unchanged |

Pure rules in `features/gallery/domain/tag_rules.py`: `TAG_BULK_PHOTO_LIMIT`,
`dedupe(ids)`, `normalise_bulk(change) -> PhotoTagsBulkChange` (raises the three `400`s),
`replace_diff(current, desired) -> TagDiff`, `bulk_diff(current, add, remove) -> TagDiff`.

## Implementation Order

Each step leaves the tree type-correct for the whole-tree mypy hook (memory: commit splitting).

0. **Specs** (in the commit with the first code step, CLAUDE.md §6.2): `specs/gallery/spec.md`
   (tags, lists, filter, `members`, feed rule, admin), `plan.md`, `tasks.md`;
   `specs/accounts/spec.md` (link, `member_id`, admin); `specs/members/spec.md` (tags, link,
   cascade, feed effect, `MemberAdmin` search); spec 012 (three routes in the `gallery`
   classification, picker as override, tagged list and filter as member endpoints, User Story 3
   and matrix note exception); the spec adjustment above.
1. **Exceptions split**: move the gallery section to `core/domain/gallery_exceptions.py` with
   explicit re-exports; existing tests (`core/tests/unit/test_gallery_exceptions.py`,
   `test_gallery_trash_exceptions.py`) pass unchanged. Then the 3 new exceptions + unit tests.
2. **Domain**: `tag_rules.py` and its unit tests; `require_int_list` in `core/http/parsing.py`
   and its tests.
3. **Models + migrations**: `PhotoTag`, `Profile.member`; `makemigrations gallery accounts`;
   migration forward/back test.
4. **Profile link**: `ProfileSerializer.member_id`; `ProfileAdmin` (autocomplete) and
   `MemberAdmin` (`search_fields`); tests (US3).
5. **`members` in the Photo resource**: `MemberRef`, `PhotoView.members`, prefetch in `_photos()`,
   `MemberRefSerializer`, `PhotoSerializer.members`; update fakes; legacy-reads test.
6. **Filter**: repository `member_ids`, `GalleryService` pass-through, views parse
   `member_id`; AND regression tests.
7. **Directory port**: `MemberDirectory` / `NamedMember` Protocols; `list_names` and
   `existing_ids` on `MemberRepositoryImpl`; tests.
8. **Tag writes and lists**: `PhotoTagRepositoryImpl`, `PhotoTagService`, DTOs, serializers,
   `views/tags.py`, URLs (`api/photos/members/` before `api/photos/<int:photo_id>/`, harmless
   either way given the `int` converter), DI; unit, API and access tests; log line.
9. **Feed hooks**: `features/gallery/signals.py`, `GalleryConfig.ready()`, wiring entry in
   `config/di.py`; feed regression tests (API and admin rename, delete, untagged, other field).
10. **Admin**: read-only `tagged_members` on `PhotoAdmin`; admin tests (incl. deleting a tagged
    member from the member admin).
11. **Access matrix**: new endpoints in `core/tests/integration/test_management_access_matrix.py`;
    Mídia picker vs `GET /api/members/`.
12. **Validation**: quickstart §1–§4, §3 against the production dump.

## Project Structure

### Documentation (this feature)

```text
specs/015-gallery-member-tags/
├── spec.md
├── plan.md                        # this file
├── research.md                    # R-01 … R-13
├── data-model.md
├── quickstart.md
├── contracts/gallery-tags-api.md
├── checklists/requirements.md
└── tasks.md                       # /speckit-tasks
```

### Source Code

```text
server/
├── config/di.py                                   # tag repo/service; member_repository as directory; wiring of gallery.signals, views.tags
├── core/
│   ├── domain/
│   │   ├── exceptions.py                          # gallery section moved out, re-exported
│   │   └── gallery_exceptions.py                  # new: moved section + 3 tag exceptions
│   ├── http/parsing.py                            # + require_int_list
│   └── tests/…                                    # parsing, exceptions, access matrix
└── features/
    ├── accounts/
    │   ├── admin.py                               # ProfileAdmin with member autocomplete
    │   ├── migrations/0005_….py                   # generated
    │   ├── models/profile.py                      # + member
    │   └── serializers/serializers.py             # + member_id (read-only)
    ├── members/
    │   ├── admin.py                               # MemberAdmin(search_fields=["name"])
    │   └── repositories/member_repository.py      # + list_names, existing_ids (MemberDirectory)
    └── gallery/
        ├── admin.py                               # read-only tagged_members on PhotoAdmin
        ├── apps.py                                # ready(): connect signals
        ├── signals.py                             # new: pre_save / pre_delete on "members.Member"
        ├── domain/tag_rules.py                    # new
        ├── dtos/
        │   ├── gallery_dtos.py                    # PhotoView.members
        │   └── tag_dtos.py                        # new
        ├── migrations/0005_….py                   # generated
        ├── models/tags.py                         # new: PhotoTag
        ├── repositories/
        │   ├── interfaces.py                      # + PhotoTagRepository, MemberDirectory, NamedMember; GalleryRepository filter
        │   ├── gallery_repository.py              # prefetch members, member_ids filter
        │   └── photo_tag_repository.py            # new
        ├── serializers/
        │   ├── serializers.py                     # PhotoSerializer.members, MemberRefSerializer
        │   └── tag_serializers.py                 # new: bodies, TaggedMemberSerializer
        ├── services/
        │   ├── gallery_service.py                 # member_ids pass-through
        │   └── photo_tag_service.py               # new
        ├── urls.py                                # 4 routes
        ├── views/
        │   ├── gallery.py                         # member_id parsing on the two reads
        │   └── tags.py                            # new: PUT, bulk POST, picker, tagged list
        └── tests/                                 # per quickstart §1
```

**Structure Decision**: tags stay in `features/gallery`, split by layer like 013 and 014, with
the model in its own `models/tags.py`. `features/members` only gains two repository methods and an
admin class; `features/accounts` a field, a serializer field and an admin class. The only
cross-feature links are the string foreign keys, the port wired in `config/di.py`, and the
lazy-sender signals.

## Dependencies (outside this repository)

- **Android app** (separate spec): shows `members`, the filter screen and "photos of me". Not
  required for the backend to ship: old versions ignore the new fields.
- **Administrator task after deploy**: link profiles to members in the Django admin, by hand.

## Out of scope, found during planning (reported, not changed)

- `Member` edits in the Django admin still bypass the members history (members spec rule 11);
  this feature only makes the gallery feed see them.
- The picker and the tagged-member list are not paginated, like every gallery list.

## Complexity Tracking

No constitution violations to justify. The two recorded deviations (signals despite the members
history rule, the exceptions split) are within the rules and were decided with the requester.
