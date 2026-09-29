# Data Model: Member Tags in Gallery Photos

State after the generated migrations `gallery/0005` and `accounts/0005` (research R-12). Models
not listed here are unchanged.

## PhotoTag (new, `features/gallery/models/tags.py`)

| Field | Type | Notes |
|-------|------|-------|
| id | int (PK, auto) | |
| photo | FK → `Photo`, `CASCADE`, `related_name="tags"` | removed by the 014 purge with its photo; kept while the photo is trashed |
| member | FK → `"members.Member"`, `CASCADE`, `related_name="+"` | removed with its member; no reverse accessor on `Member` |
| tagged_by | FK → user, null, `SET_NULL`, `related_name="+"` | auditing only, never serialized |
| tagged_at | DateTimeField | from the injected `Clock`; auditing only, never serialized |

- Constraint `unique_photo_tag`: `UNIQUE (photo, member)`. Its index also serves "tags of these
  photos"; the foreign key's own index serves "photos of this member".
- `Meta.ordering = ["photo_id", "member_id"]`, `verbose_name = "photo tag"`,
  `__str__` → `"{photo_id}:{member_id}"` (ids only, never a name).
- Not registered in the Django admin (R-09).
- Visibility follows the photo: every read filters on the photo being live (the live manager when
  starting from `Photo`; an explicit `photo__deleted_at__isnull=True` when starting from
  `PhotoTag`, R-08).

## Profile (extended, `features/accounts/models/profile.py`)

| Field | Type | Notes |
|-------|------|-------|
| member | OneToOne → `"members.Member"`, null, blank, `SET_NULL`, `related_name="profile"` | set only in the Django admin; unique, so one profile per member |

`is_member` is unchanged and independent (FR-005).

## Member (unchanged in shape)

Gains two reverse effects, no column:

- `member.profile` (reverse of `Profile.member`).
- Deleting a member cascades to its `PhotoTag` rows and sets `Profile.member` to null.
- `MemberAdmin` is registered with `search_fields = ["name"]` (needed by the profile's
  autocomplete, R-02).

## Photo (unchanged in shape)

Its resource gains `members`; its `updated_at` is now also set by tag writes and by the rename or
deletion of a tagged member (R-07).

## DTOs (Pydantic, `features/gallery/dtos/tag_dtos.py` unless noted)

| DTO | Fields | Used by |
|-----|--------|---------|
| `MemberRef` | `id: int`, `name: str` | `PhotoView.members`, the picker |
| `TaggedMember` | `id: int`, `name: str`, `photo_count: int` | tagged-member list |
| `PhotoMembersReplace` | `member_ids: list[int]` | `PUT …/members/` |
| `PhotoTagsBulkChange` | `photo_ids: list[int]`, `add_member_ids: list[int]`, `remove_member_ids: list[int]` | bulk `POST` |
| `PhotoView` *(gallery_dtos.py, extended)* | + `members: list[MemberRef] = []` (last) | every Photo resource |

Domain values (frozen dataclasses in `features/gallery/domain/tag_rules.py`, so the domain never
imports the DTO layer): `BulkTagRequest` (`photo_ids`, `add_member_ids`, `remove_member_ids`,
after normalisation) and `TagDiff` (`added`, `removed`: photo id → member ids; properties
`changed_photo_ids`, `is_empty`), used by the service, the tag repository and the log line.

## Ports

| Protocol | Where declared | Implemented by | Methods |
|----------|----------------|----------------|---------|
| `PhotoTagRepository` | `features/gallery/repositories/interfaces.py` | `PhotoTagRepositoryImpl` (`repositories/photo_tag_repository.py`) | `lock_live_photos(ids) -> list[int]`, `current_tags(photo_ids) -> dict[int, set[int]]`, `write_diff(diff, actor_id) -> None` (inserts, deletes, and sets `updated_at` on the changed photos), `tagged_members() -> list[TaggedMember]`, `touch_photos_if_renamed(member_id, new_name) -> None`, `touch_photos_of_member(member_id) -> None` |
| `MemberDirectory` | `features/gallery/repositories/interfaces.py` | `MemberRepositoryImpl` (`features/members`; the two methods are not added to members' own `MemberRepository` Protocol, which `MemberService` does not need them in) | `list_names() -> Sequence[NamedMember]` (every member, by name then id), `existing_ids(ids) -> set[int]` |
| `NamedMember` | same | `MemberDTO` (structurally) | read-only `id: int`, `name: str` |
| `GalleryRepository` *(extended)* | same | `GalleryRepositoryImpl` | `list_all_photos(member_ids=frozenset())`, `list_photos_by_album(album_id, member_ids=frozenset())` |

## Validation rules

| Rule | Where | Error |
|------|-------|-------|
| repeated ids dropped | service, before any query | — |
| `photo_ids` non-empty; `add_member_ids ∪ remove_member_ids` non-empty | service | `ValidationError` (`400`) |
| at most `TAG_BULK_PHOTO_LIMIT = 200` distinct photos | service (`features/gallery/domain/tag_rules.py`) | `TagBulkLimitError` (`400`) |
| no id in both member lists | service | `TagListOverlapError` (`400`) |
| every photo live, every member existing | service, inside the transaction | `PhotoTagReferenceError` (`404`) |
| `PUT` route photo live | service | `PhotoNotFoundError` (`404`) |
| `member_id` query values are integers | view (`require_int_list`) | `ValidationError` (`400`) |
| body lists are lists of integers | serializers | DRF validation → `VALIDATION_ERROR` (`400`) |

## State transitions of a tag

```text
(none) --PUT/POST add--> tagged --PUT/POST remove--> (none)
tagged --photo trashed--> hidden --photo restored--> tagged
hidden --photo purged--> (none)
tagged | hidden --member deleted--> (none)
```
