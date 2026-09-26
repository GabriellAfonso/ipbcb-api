# Research: Members Management for Church Leaders

Decisions taken while planning `spec.md`. Each entry: decision, rationale, alternatives.
Inputs fixed by the user (routes, `MemberChangeLog` columns, `IsAdminUser`, no signals,
`on_commit` deletion) are not re-litigated here; only how to build them.

---

## R-01 Where the transaction lives

**Decision**: The services open `transaction.atomic()` and register `transaction.on_commit`
callbacks. Repositories do not open transactions of their own for these flows.

**Rationale**: The spec requires the edit and its history rows to commit or fail together
(FR-013), and those touch two repositories (`MemberRosterRepository`,
`MemberChangeLogRepository`). Only the service sees both. Precedent:
`RegisterPlaysService` and `HymnalHistoryIngestService` already call `transaction.atomic()`.
The user's decision also names the service explicitly.

**Testing consequence**: `atomic` needs a database connection, so service tests carry
`@pytest.mark.django_db` while still using named fake repositories and a fake storage;
`on_commit` callbacks are asserted with `django_capture_on_commit_callbacks`. The rules that
matter most (diff, rendering, date checks) are pure functions tested without a database.
The existing atomic-using services have no service-level unit tests at all; this is stricter.

**Alternatives**: A unit-of-work Protocol wrapping `atomic`/`on_commit` — would let service
tests skip the database, but no other service does it and it adds a seam used by one feature. One repository method doing edit +
history — hides the history write inside persistence, where the diff logic does not belong.

---

## R-02 Computing the history rows

**Decision**: A pure function `diff_member_records(before, after) -> list[MemberFieldChange]`
in `features/members/domain/member_changes.py`, plus `render_history_value(...)` for the text
form (FR-016). The service takes a `MemberRecordDTO` snapshot before the write, re-reads after,
and diffs the two.

**Rationale**: Diffing snapshots instead of the request body gives FR-015 for free: a field
sent with its current value produces no row. Rendering from the snapshot means FK and ministry
names are the ones stored at edit time. Pure, so it is unit-tested without a DB.

**Alternatives**: Diffing the model instance's field values in the repository — mixes rendering
rules into persistence. Tracking dirty fields on the model — needs a mixin or signals, both
rejected.

Rendering rules (FR-016): FK -> name; ministries -> names sorted, joined with `", "`, empty ->
`None`; `date` -> `isoformat()`; `bool` -> `"true"`/`"false"`; gender -> code; `""` or `None`
-> `None`. Field keys in history are the model field names (`status`, `role`, `ministries`,
not `status_id`), since they name what changed, not the write payload.

---

## R-03 Partial update: "not sent" vs "sent as null"

**Decision**: `MemberPatchDTO` (Pydantic, `StrictBaseModel`) with every field optional; the
service applies only `model_fields_set`. A field present with `null` clears it (status, role,
dates, gender); `name` cannot be null or blank.

**Rationale**: Pydantic already records which fields were set, so "clear status" (FR-US2.6)
and "leave status alone" are distinguishable without a sentinel type.

**Alternatives**: DRF `partial=True` serializer's `validated_data` passed on as a dict —
violates the DTO rule (CLAUDE.md §7).

---

## R-04 Validation split

**Decision**:
- **Serializer (view layer)**: shape only. Explicit fields; types; `name` max 255 and not
  blank on create; `gender` in `M`/`F`; ids are integers; `ministry_ids` a list of integers.
  Body passed through `require_object_body` first.
- **Service (domain)**: existence of status/role/ministry ids (via repository lookups that are
  needed anyway for history names), dates not in the future, baptism not before birth against
  the merged record. Raises `core.domain.exceptions.ValidationError` naming the offending value
  (CLAUDE.md §8).
- **Clock**: injected `Clock` (`core.time.clock`) for "today", so future-date tests are
  repeatable.

**Rationale**: DRF `PrimaryKeyRelatedField` would put ORM querysets into the serializer
(view layer), against "repositories are the only layer that touches the ORM". The merged-record
date check needs the current row, which only the service has.

**Messages**: Portuguese — they reach the leader's screen through the canonical error body,
same convention as `core.files.image_validation`.

---

## R-05 Photo write and cleanup ordering

**Decision** (`MemberPhotoService.replace_photo`):
1. `detect_image_extension(upload)` — reject before touching anything (FR-021).
2. `photo_storage.save(extension, upload) -> stored_name` (`members/<uuid4 hex>.<ext>`),
   outside the transaction.
3. `transaction.atomic()`: lock-free read of the old name, set the new name on the row, write
   the `photo` / "photo changed" history row, register
   `on_commit(lambda: photo_storage.delete(old_name), robust=True)` when there was an old file.
4. If step 3 raises: `photo_storage.delete(stored_name)`, re-raise.

`remove_photo` and member delete: same `on_commit(..., robust=True)` deletion of the old name.

**Rationale**: Storage cannot join a DB transaction, so the order is chosen so that every
failure leaves a consistent row: the row never points at a missing file. `robust=True`
(Django ≥ 4.2) logs and swallows a storage error in the callback, so a failed file delete after
a committed change cannot turn a successful request into a 500; the worst case is an orphan file
in a leader-only folder (spec, Edge Cases).

**Alternatives**: Deleting the old file before saving the new one (what `ProfileService` does)
— loses the photo if the save fails, which the spec forbids. Signals `pre_save`/`post_delete`
(what `Profile` uses) — rejected by the user.

---

## R-06 Photo storage behind a Protocol

**Decision**: `MemberPhotoStorage` Protocol (`save(extension, upload) -> str`,
`delete(name) -> None`, `url(name) -> str`) implemented by `DefaultStorageMemberPhotoStorage`
on `django.core.files.storage.default_storage`. `Member.photo` is an `ImageField` with
`upload_to` fixed to `members/`; the repository sets the field to the stored name without
re-saving the file.

**Rationale**: Named fake for unit tests (CLAUDE.md §10), storage is external I/O. Writing via
the storage directly (not `FieldFile.save(save=True)`) keeps the row update inside the
service's transaction and separate from the file write (R-05). Streaming: `storage.save` with
a `File` writes in chunks, same as profile photos.

**Alternatives**: `FieldFile.save(name, file, save=True)` — saves the row immediately, outside
the history transaction.

---

## R-07 Editor display name in history

**Decision**: `MemberChangeLog.editor` is a FK to `settings.AUTH_USER_MODEL` (string reference,
no Python import of `features.accounts`). The history repository reads
`editor__profile__name` through `select_related`, falling back to `editor__username` when the
profile name is blank. Editor id is the user's UUID as a string.

**Rationale**: `Profile.name` is the name the app shows for a user everywhere else. The lookup
is an ORM path inside the repository — no cross-feature import (constitution: "Features never
import from each other directly"). One query for the whole history (no queries in loops).

**Alternatives**: Snapshotting the editor name into the row — adds a column the user did not
list, and the spec says a deleted editor shows as unknown. `User.get_full_name()` — not the name
the app displays.

---

## R-08 Response caching

**Decision**: Every leader GET returns through `_not_modified_or_response(request, body,
private=True)`: `Cache-Control: private, no-store`, `Vary: Authorization`, ETag/304 (FR-007).

**Rationale**: Existing helper; constitution Caching rule. Leader data must never land in a
shared cache.

---

## R-09 Logging

**Decision**: One structured line per write: `logger.info("member_created" |
"member_updated" | "member_deleted" | "member_photo_replaced" | "member_photo_removed",
extra={"member_id": id, "editor_id": str(user_id), "changed_fields": n})`. `changed_fields` is a
count, not names. No log on reads.

**Rationale**: FR-028: member id only, never member data. Field names are not member data,
but a count is enough for observability and removes the question.

---

## R-10 Errors

**Decision**: New `MemberNotFoundError(NotFoundError)` in `core/domain/exceptions.py`
(`error_code` inherited `NOT_FOUND`, message includes the id). Validation reuses
`ValidationError`. No handler change: both map by `isinstance`.

**Rationale**: Same pattern as `ProfileNotFoundError`, `SongsNotFoundError`.

---

## R-11 Naming and file split

**Decision**: Services `MemberRosterService` (list, get, create, update, delete, options),
`MemberPhotoService` (replace, remove), `MemberChangeLogService` (read history). Repositories
`MemberRosterRepository`, `MemberChangeLogRepository`, `MemberPhotoStorage`. The existing
`MemberService`/`MemberRepository` (regular list, birthdays) stay untouched.

**Rationale**: Keeps each file under 500 lines and each class to one responsibility (CLAUDE.md
§8). Names are grep-unique; "roster" distinguishes the leader flows from the existing
member-facing `MemberService`.

---

## R-12 Django admin bypass — OPEN, for the user

`admin.site.register(Member, ...)` stays. An edit or delete made in the Django admin writes no
history (no service involved, no signals by decision) and a delete there leaves the photo file
on disk. Default in this plan: **leave as is and document it** in the domain spec. Alternatives
the user may prefer: make `Member` read-only in the admin, or unregister it. Not decided here
(trade-off for the user).

---

## R-13 Found during planning, out of scope

- `Member`, `MemberStatus`, `Role`, `Ministry` lack `Meta.ordering` / `verbose_name` required
  by the constitution (Code Standards). Adding them produces an `AlterModelOptions` migration
  and changes default query order; not done here.
- `.specify/memory/constitution.md` differs from `specs/constitution.md` (stale copy).
- `/api/members/` and `/api/members/birthdays/` send no cache headers although their bodies are
  member-only. Not per-caller, so the constitution does not require `private` — reported only.
