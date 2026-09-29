# Research: Member Tags in Gallery Photos

Decisions behind [plan.md](plan.md). Each entry: decision, rationale, alternatives rejected.
Code references are to the state after feature 014.

---

## R-01 Where a tag lives

**Decision**: A new model `PhotoTag` in `features/gallery/models/tags.py`: `photo` (FK `Photo`,
`CASCADE`, `related_name="tags"`), `member` (FK `"members.Member"` by string, `CASCADE`,
`related_name="+"`), `tagged_by` (FK user, `SET_NULL`, null, `related_name="+"`), `tagged_at`
(DateTimeField from the injected clock). Unique constraint `(photo, member)`.

**Rationale**: Tags belong to the gallery: they are written by gallery managers, shown in the
Photo resource and hidden with a trashed photo. `CASCADE` from `Photo` makes the 014 purge remove
tags with the row without touching the purge code (FR-009); a trashed photo keeps its row, so its
tags stay (FR-009). `CASCADE` from `Member` removes tags with a member on every path, the Django
admin included. The string reference follows `features/schedule/models/schedule.py`, which
already points at `"members.Member"` without importing it. `related_name="+"` keeps
`features/members` free of a reverse accessor into the gallery, as `MemberChangeLog.editor` does
for `accounts.User`. An explicit model (not an implicit `ManyToManyField` table) carries the audit
fields of FR-010.

**Alternatives**:
- *`ManyToManyField(Member)` on `Photo`*: the implicit through table has no room for `tagged_by`
  and `tagged_at`, and `photo.members` would invite ORM writes outside the service.
- *`PROTECT` on `member`*: would block deleting a tagged member, contradicting FR-009.
- *Tag model in `features/members`*: members would learn about photos, and the gallery would have
  to ask another feature for its own resource.

## R-02 Profile link

**Decision**: `Profile.member = OneToOneField("members.Member", null=True, blank=True,
on_delete=SET_NULL, related_name="profile")`. `ProfileSerializer` adds `member_id` to `fields` and
to `read_only_fields`. The Django admin registers `ProfileAdmin` with
`autocomplete_fields = ["member"]`; `features/members/admin.py` registers `MemberAdmin` with
`search_fields = ["name"]`, which autocomplete requires.

**Rationale**: The one-to-one's unique index enforces "a member has at most one profile" in the
database, and the admin form's `validate_unique()` turns a second link into a form error with
nothing saved (FR-002, US3-3). `SET_NULL` keeps the profile and its user when the member is
deleted (FR-004). A read-only serializer field makes DRF ignore `member_id` in `PATCH`, the same
way it ignores `is_member` today (FR-003). The related name is the one the request asked for.

**Alternatives**:
- *`ForeignKey` with `unique=True`*: same effect, and Django warns to use `OneToOneField`.
- *A plain `raw_id_fields` widget*: meets "no scrolling" but asks the administrator for a numeric
  id; autocomplete searches by name (US3-4).

## R-03 Reading member data from the gallery without importing `features/members`

**Decision**: Two paths, by what the data is.

1. **Names of tagged members** (the Photo resource's `members`, the tagged-member list) are read
   by gallery repositories through the `PhotoTag.member` relation (`member__name`), with no import
   of `features/members`.
2. **The roll itself** (the picker: every member, tagged or not; existence of the ids in a tag
   write) goes through a port. `features/gallery/repositories/interfaces.py` declares
   `MemberDirectory` (Protocol): `list_names() -> list[NamedMember]` and
   `existing_ids(ids) -> set[int]`, where `NamedMember` is a Protocol with read-only `id: int` and
   `name: str`. `features/members/repositories/member_repository.py` implements both methods on
   `MemberRepositoryImpl` (returning its existing `MemberDTO(id, name)`, which satisfies
   `NamedMember` structurally). `config/di.py` hands `member_repository` to the gallery tag
   service.

**Rationale**: Same boundary rule as 014 R-05 (media ↔ gallery): the consumer owns the port,
the provider implements it structurally, the composition root wires them, and neither feature
imports the other. The relation traversal of (1) is the same coupling the `PhotoTag` foreign key
already is (R-01); the picker of (2) is a read of the roll, which only `features/members` should
query.

**Alternatives**:
- *Picker through `PhotoTag._meta.get_field("member").related_model`*: no import, but it is ORM
  introspection standing in for a dependency, and `features/gallery` would be querying the roll.
- *Everything through the port, names included*: every photo list would need a second query and
  an in-memory join, for data the relation already gives in the same prefetch.

## R-04 Tag writes: locking, atomicity, errors

**Decision**: `PhotoTagService` runs each write in one `transaction.atomic()`:

1. Normalise: drop repeated ids (FR-016); for the bulk request, refuse `len(photo_ids) == 0`,
   both member lists empty, an id in both lists (FR-018), or more than
   `TAG_BULK_PHOTO_LIMIT = 200` photos (FR-017) — all `400` before any query.
2. Lock the live photo rows, `select_for_update()` ordered by id (so two bulk requests over
   overlapping photos cannot deadlock), through the live manager.
3. Collect every offending id: photos not returned by step 2 (unknown **or** trashed — 014 treats
   a trashed id as nonexistent everywhere outside the trash) and members not in
   `MemberDirectory.existing_ids`. Any offending id raises `PhotoTagReferenceError` (`404`
   `NOT_FOUND`, `missing_photo_ids`, `missing_member_ids`), nothing written.
4. Compute the diff per photo against the current tags, insert the missing pairs
   (`bulk_create(ignore_conflicts=True)`), delete the removed pairs, and set `updated_at` on the
   photos whose set changed — only those (FR-019, FR-028).

`PUT /api/photos/{id}/members/` on an unknown or trashed photo in the route raises
`PhotoNotFoundError` (`404`, `photo_id`), as every 013 route does.

**Rationale**: The photo row lock serialises concurrent writes on the same photo, so each request
applies as a whole (Edge Cases). One error listing every offending id lets the app fix them in
one go. `404` matches 013, where unknown ids referenced in a body (`parent_id`, `album_id`) are
`404`; trashed ids are merged with unknown ones, as 014 merges them into an order request's
`unexpected`, so a caller with `manage` (not `owner`) does not learn what is in the trash. A member
deleted between step 3 and step 4 makes the insert fail on its foreign key; the service catches
the `IntegrityError`, re-reads `existing_ids` and raises `PhotoTagReferenceError` (Edge Cases:
"never leaves a tag pointing at nothing").

**Alternatives**:
- *Separate `trashed_photo_ids` in the error*: reveals trash contents to `manage`, which 014
  reserves for `owner`.
- *`400` for body references*: breaks the 013 convention for the same kind of mistake.
- *Locking the member rows*: would need the members table locked from the gallery; the foreign
  key already guarantees no dangling tag, and the retry path turns the rare race into the normal
  error.

## R-05 Filter by members (AND)

**Decision**: `GalleryRepository.list_all_photos(member_ids)` and
`list_photos_by_album(album_id, member_ids)` take an optional set. When it is non-empty the query
adds
`filter(tags__member_id__in=ids).annotate(matched=Count("tags__member", filter=Q(tags__member_id__in=ids), distinct=True)).filter(matched=len(ids))`.
The view reads `request.query_params.getlist("member_id")` and parses each value with a new
`core.http.parsing.require_int_list(values, field)`, which raises the canonical
`VALIDATION_ERROR` naming the first bad value (FR-023).

**Rationale**: One join whatever the number of members, and the photo list keeps its ordering
(tree order in the service for `GET /api/photos/`, position then id for an album). Chained
`.filter(tags__member_id=x)` per member also gives AND, but adds one join per member; with no cap
on the number of values in the spec, the count form keeps the query shape fixed. Unknown ids
simply match nothing (FR-023). The live manager already excludes trashed photos.

**Alternatives**:
- *Filter in Python after loading every photo*: correct but loads the whole gallery for every
  filtered read.
- *A cap on the number of `member_id` values*: not asked for, and unnecessary with the count form.

## R-06 The Photo resource's `members`

**Decision**: `PhotoView` gains `members: list[MemberRef]` (`MemberRef(id, name)`, a gallery
DTO). `_photos()` in `GalleryRepositoryImpl` adds
`prefetch_related(Prefetch("tags", queryset=PhotoTag.objects.select_related("member").order_by("member__name", "member_id")))`,
and `_to_view` builds the list. `PhotoSerializer` adds `members` (a nested
`MemberRefSerializer` with exactly `id` and `name`) as its last field. Every path that returns a
Photo resource already builds it through `_to_view` (list, album list, upload, patch, restore,
feed, tag writes), so each gains the field without another change.

**Rationale**: Two queries for any number of photos (the list, then every tag with its member).
The serializer lists its fields explicitly (FR-033). Last position keeps every older field where
old app versions read it (FR-011).

**Alternatives**:
- *Annotate names with a subquery aggregate (string_agg)*: database-specific (SQLite in tests,
  PostgreSQL in production) and loses the ids.

## R-07 The feed learns about tag writes, renames and deletions

**Decision**:

- **Tag writes** set `updated_at` on the photos whose tags changed, inside the write (R-04).
- **Renames and deletions of members** are caught by `features/gallery/signals.py`, connected in
  `GalleryConfig.ready()` with the lazy sender string `"members.Member"` (no import):
  - `pre_save`: skipped for `raw` saves (fixtures) and for saves whose `update_fields` excludes
    `name`. Otherwise it calls `PhotoTagRepository.touch_photos_if_renamed(member_id, new_name)`:
    one query checks whether the member has any tag whose stored `member__name` differs from
    `new_name` (the row still holds the old name), and only then one `UPDATE` sets `updated_at`
    on the member's live tagged photos.
  - `pre_delete`: `PhotoTagRepository.touch_photos_of_member(member_id)`, before `CASCADE`
    removes the tags.
  The handlers are thin, module-level and injected (like `_album_service` in
  `features/gallery/admin.py`); the ORM stays in the repository.

**Rationale** (decided with the requester, 2026-09-29): FR-026 requires every path — the members
management API, the Django admin form, the admin's bulk delete action and anything else that
saves or deletes a `Member`. Model signals are the one hook all of them go through:
`MemberRosterRepositoryImpl.update` uses `save(update_fields=…)` and `delete` uses
`QuerySet.delete()`, which sends `pre_delete` per row when a receiver exists. The members spec's
"No signals" rule is about the change history, which needs the editor; here the editor does not
matter. Bumping in `pre_save`/`pre_delete` runs inside the caller's transaction (the roster
service and the admin are atomic); if a caller is not atomic and its write fails, the photos are
reported once more, which the feed's idempotent client already tolerates (014 R-07). Photos in the
trash are not bumped; their restore bumps them already (014 FR-020). A member tagged nowhere costs
one indexed query per save and none per delete of an untagged member beyond one `UPDATE` that
matches no row.

**Alternatives**:
- *A port in `features/members` (`MemberChangeListener`) called by the roster service and by a
  custom `MemberAdmin` (`save_model`, `delete_model`, `delete_queryset`)*: explicit, but more
  code and misses the shell and any future path; rejected by the requester.
- *Derived "change time" at read time* (max of the photo's `updated_at`, its tags' times and a
  `name_changed_at` on `Member`): deletions leave nothing to read, so it would need a tombstone
  table anyway, and every feed query would join three tables.

## R-08 The two member lists

**Decision**:

- **Picker** (`GET /api/gallery/taggable-members/`): `PhotoTagService.taggable_members()` returns
  `MemberDirectory.list_names()` ordered by name then id, mapped to `MemberRef`. Permission
  `[IsAuthenticated, scope_permission(Scope.GALLERY, {"GET": Level.MANAGE})]`.
- **Tagged-member list** (`GET /api/gallery/tagged-members/`):
  `PhotoTagRepository.tagged_members()` —
  `PhotoTag.objects.filter(photo__deleted_at__isnull=True).values("member_id", "member__name").annotate(photo_count=Count("photo_id")).order_by("member__name", "member_id")`.
  Permission `IsMemberUser`.

Both responses use `_not_modified_or_response(request, data, private=True)`
(`Cache-Control: private, no-store`, `Vary: Authorization`, ETag/`304`).

**Rationale**: The explicit `photo__deleted_at__isnull=True` is needed because a filter that
starts from `PhotoTag` and crosses the relation does not go through `Photo`'s live default manager
(014 R-02) — the one place in this feature where the live-only default does not protect by itself
(FR-012, SC-005). `private` is defence in depth for FR-034: an authenticated response without
cache headers is not stored by a compliant shared cache anyway, but the members domain declares
its management responses private, and these carry names from the roll; the ETag keeps the app's
repeated reads cheap.

**Alternatives**:
- *Picker from the tags*: would offer only people already tagged, making the first tag
  impossible.
- *Counting through `Photo.objects`* (`Photo.objects.filter(tags__member_id=…)` grouped by
  member): live by default, but grouping by a related field from the photo side is harder to
  read than the one-line `PhotoTag` query with the explicit filter.

## R-09 Tags in the Django admin

**Decision**: `PhotoAdmin` gains a read-only method field `tagged_members` listing the names
(ordered as in the resource). `PhotoTag` is not registered in the admin. No inline.

**Rationale**: Clarified: read-only (spec FR-029). Not registering `PhotoTag` also keeps the
Member delete confirmation page free of a permission check on tags (the admin checks delete
permission only for registered models), so deleting a member there works as today.

## R-10 Exceptions and the 500-line rule

**Decision** (decided with the requester, 2026-09-29): the gallery section of
`core/domain/exceptions.py` (`AlbumNotFoundError` through `AlbumRestoreNameConflictError`, ~200
lines) moves to `core/domain/gallery_exceptions.py`, and `core/domain/exceptions.py` re-exports
each name explicitly, so no import changes anywhere. The new exceptions go to the new module:

| Exception | Base | `error_code` | `extra_context` |
|-----------|------|--------------|-----------------|
| `PhotoTagReferenceError` | `NotFoundError` | `NOT_FOUND` | `missing_photo_ids`, `missing_member_ids` |
| `TagBulkLimitError` | `ValidationError` | `VALIDATION_ERROR` | `photo_count`, `limit` |
| `TagListOverlapError` | `ValidationError` | `VALIDATION_ERROR` | `member_ids` |

An empty bulk request (no photo, or no member in either list) raises a plain `ValidationError`
naming the field and the expected shape.

**Rationale**: `exceptions.py` is at 465 lines; the three new classes (~60 lines) would pass the
500-line limit (CLAUDE.md §8). Moving one domain's section is the smallest split that keeps the
single import path CLAUDE.md names.

**Alternatives**:
- *Package `core/domain/exceptions/` with one module per domain*: cleaner long-term, touches every
  domain at once; rejected by the requester for now.

## R-11 Logging

**Decision**: One line per tag write that changed at least one tag, event
`gallery_tags_changed`, fields `photo_ids` (changed photos), `added` and `removed`
(`{photo_id: [member_id, …]}`, only non-empty entries), `actor_id`. A write that changes nothing
logs nothing. The signal handlers log nothing (a rename or deletion is logged by the members
domain already, and the photo bump is not a tag change).

**Rationale**: Ids only (constitution, members data protection; FR-033, FR-036). Logging no-op
writes would add lines that say nothing happened.

## R-12 Migrations

**Decision**: Two generated migrations: `gallery/0005` (`PhotoTag`, depends on the latest
`members` migration) and `accounts/0005` (`Profile.member`, same dependency). No data migration
(FR-045). Verification on a restored production dump with a real rollback, as in 013 and 014.

**Rationale**: Both are pure additions (a new table, a nullable column with a unique index), so
`makemigrations` expresses them exactly and the rollback drops them.

## R-13 Order of responses

**Decision**: `PUT` answers the one Photo resource. The bulk request answers the Photo resources
of the listed photos in the order of their first appearance in `photo_ids`. The picker and the
tagged-member list are ordered by name, then id; the Photo resource's `members` likewise.

**Rationale**: The app matches the answer to its selection in the order it sent; ties by id make
every order total.
