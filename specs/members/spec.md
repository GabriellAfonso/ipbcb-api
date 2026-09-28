# Members Domain Spec

The church membership roll: who the members are, their standing on the roll, their role and
ministries. Regular members read a minimal view of it (names, birthdays); church leaders manage
it in full, with an edit history.

Member data is **sensitive personal data** (LGPD art. 11: religious affiliation tied to a named
person). Every rule marked *(data protection)* below exists because of that.

Leader management was added by `specs/010-members-management/`. Birth date split into day,
month and year by `specs/011-split-birth-date/`.

---

## Data Models

### MemberStatus
- `name`: string, max 50, unique
- Says whether a member is communicant or not (and similar roll states). This is the only
  place that answer lives — there is no separate "communicant" field.
- The roll uses exactly these statuses, named after the IPB *Manual Presbiteriano* (names are
  user-facing, so they stay in Portuguese):
  - `Comungante` — professing member, takes communion.
  - `Não comungante` — member not yet professing (baptized child of believers).
  - `Ausente` — member kept apart from the active roll for absence (the Manual's "rol
    separado"; the plain word is used because the official one is unclear to most users).
  - `Visitante` — attends occasionally, not a member.
- Code never branches on these names; they are data rows edited in the Django admin.

### Role
- `name`: string, max 100, unique — the member's office in the church

### Ministry
- `name`: string, max 100, unique

Statuses, roles and ministries are managed in the Django admin only.

### Member
- `name`: string, max 255, required — display name
- `first_name`, `last_name`: string, max 255, blank allowed (default `""`)
- `birth_day`, `birth_month`, `birth_year`: small integers, each nullable. Independent parts
  so a partly known birth date is stored as exactly what is known: full date, day+month only,
  year only, or nothing. Day and month are both set or both empty. There is no placeholder
  year (the old year-0001 convention for "year unknown" became an empty year in
  `specs/011-split-birth-date/`). Database check constraints enforce the day/month pair, day
  1-31 and month 1-12, so the Django admin cannot store half a birthday either.
- `gender`: `M` | `F`, nullable
- `status`: FK -> MemberStatus, nullable, `SET_NULL`
- `role`: FK -> Role, nullable, `SET_NULL`
- `ministries`: M2M -> Ministry, blank allowed
- `baptism_date`: date, nullable
- `is_active`: bool, default true — means **"valid profile"**. Keeps its name; the meaning is
  stated in a model comment. Only valid profiles appear in the regular member list
  and in birthdays.
- `created_at`: datetime, set on creation
- `photo`: image, nullable. Stored at `members/{uuid4().hex}.{ext}`, `ext` from the
  decoded image format. No member name or id in the path. Independent of `Profile.photo`:
  never shared, copied or reused between the two. Readable only by leaders, through the media
  access rule for `members/` (`specs/009-protected-media-access/`).

### MemberChangeLog
- `member`: FK -> Member, `CASCADE` (a member's history is deleted with it, no anonymisation)
- `editor`: FK -> User, nullable, `SET_NULL` (history survives the editor's account deletion)
- `field`: string — a Member field name, or `created`, or `photo`. Entries written before
  feature 011 may carry `birth_date`; they are kept as they are.
- `old_value`, `new_value`: text, nullable
- `changed_at`: datetime, set on creation
- Own table, not `django-simple-history`.

---

## DTOs (Pydantic)

| DTO | Fields | Used by |
|-----|--------|---------|
| `MemberDTO` | id, name | Regular member list |
| `BirthdayDTO` | name, gender, birth_month, birth_day | Birthdays |

Leader DTOs (`NamedRefDTO`, `MemberSummaryDTO`, `MemberRecordDTO`, `MemberCreateDTO`,
`MemberPatchDTO`, `MemberFieldChange`, `ChangeLogEntryDTO`, `MemberOptionsDTO`): fields in
`specs/010-members-management/data-model.md`. Writes send `status_id`, `role_id`,
`ministry_ids`; `MemberPatchDTO` applies only the fields sent.

---

## Endpoints

### GET `api/members/`
- `IsAuthenticated` + `IsMemberUser`
- Returns `{"members": [{"id", "name"}]}`, valid profiles only (`is_active=True`), ordered by
  name

### GET `api/members/birthdays/?month=M` or `?month=M-M`
- `IsAuthenticated` + `IsMemberUser`
- `month`: single month (`7`) or inclusive range (`1-6`), each 1-12, start <= end
- Returns `{"birthdays": [{"name", "gender", "birth_month", "birth_day"}]}`, valid profiles
  with both `birth_day` and `birth_month` set and the month in the range, ordered by month then
  day. Members with only a year, or no birth information, never appear. 29/02 is shown as day
  29 in every year.
- Invalid `month`: 400

### Leader endpoints

All `IsAuthenticated` + `IsAdminUser` (leader = `Profile.is_admin`; no leader-named class). Prefixed
`/admin/` because `api/members/` already serves regular members. GET responses are private:
`Cache-Control: private, no-store`, `Vary: Authorization`, with ETag/304.

| Method | Route | Does |
|---|---|---|
| GET | `api/admin/members/` | Every member (valid or not), no pagination or search, ordered by name: id, name, photo_url, status `{id, name}` or null, is_active |
| POST | `api/admin/members/` | Create; `name` required. Returns the full record (201). History: one `created` row |
| GET | `api/admin/members/{id}/` | Full record: id, name, first_name, last_name, birth_day, birth_month, birth_year, gender, status, role, ministries `[{id, name}]`, baptism_date, is_active, photo_url, created_at |
| PATCH | `api/admin/members/{id}/` | Partial edit of name, first_name, last_name, birth_day, birth_month, birth_year, gender, status, role, ministries (full replacement), baptism_date, is_active. Returns the full record. History: one row per changed field |
| DELETE | `api/admin/members/{id}/` | Deletes member, its history and its photo file (204). No soft delete |
| PUT | `api/admin/members/{id}/photo/` | Multipart `photo`. Upload/replace. Returns photo_url. History: `photo`, "photo changed" |
| DELETE | `api/admin/members/{id}/photo/` | Remove photo (204). History: `photo`, "photo removed". No photo: 204, no history |
| GET | `api/admin/members/{id}/history/` | Newest first: editor `{id, name}` or null, field, old_value, new_value, changed_at |
| GET | `api/admin/members/options/` | `{"statuses", "roles", "ministries"}`, each `[{id, name}]` ordered by name |

---

## Business Rules

1. Only valid profiles (`is_active=True`) appear in the regular member list and birthdays.
   Leaders see every record.
2. Write validation: `name` non-blank; status, role and ministry ids must exist;
   gender `M`/`F`; baptism date not in the future. All checked against the record as it would
   be after the edit. Birth parts:
   - day 1-31, month 1-12, year from 1 (whole numbers);
   - day and month both set or both empty; year independent;
   - day and month form a real calendar date; 29/02 only with an empty or leap year;
   - year not after the current year; a full date not after today (day+month alone is never
     "in the future");
   - baptism not before birth, on what is known: full date vs `baptism_date`; year only vs the
     baptism year; no check with day+month only.
3. History is written by the service, in the same `transaction.atomic` as the change.
   No signals: they do not know the editor and bypass the service layer. A rejected write
   leaves no history.
4. History values are text: FKs and ministries by name as of edit time, dates
   `YYYY-MM-DD`, birth parts as plain numbers (each part its own field), booleans `true`/`false`, gender as its code, empty as null. Ministries: one row
   per edit, names sorted and joined by `", "` (e.g. `"A, B"` -> `"A, C"`). Photo rows carry
   only the marker, never a file path. Fields sent unchanged write nothing.
5. Reads are never recorded.
6. Photo uploads go through `core.files.image_validation` (decoded content, JPEG/PNG/
   WEBP/GIF, 10 MB), validated before anything is replaced.
7. Old photo files are deleted from storage on replace, photo removal and member
   delete, only after the transaction commits (`transaction.on_commit`). If the database write
   fails, the newly stored file is removed and the old photo stays.
8. Delete confirmation (typing the member's name) is the app's job; the backend
   deletes on request.
9. *(data protection)* Serializers list fields explicitly, never `"__all__"`.
10. *(data protection)* Structured logs carry `member_id` only, never member data. Each
    write logs one line (`member_created`, `member_updated`, `member_deleted`,
    `member_photo_replaced`, `member_photo_removed`) with `member_id`, `editor_id` and a
    `changed_fields` count.
11. **Known limitation — Django admin.** `Member` is still registered in the Django admin,
    which bypasses the service: an edit there writes no history, skips the calendar, future
    and baptism-before-birth checks (only the database constraints apply), and a delete there
    leaves the photo file on disk (in the leader-only `members/` folder). The leader endpoints are the
    supported path.

---

## Errors

| Scenario | Status | `error_code` |
|---|---|---|
| Not authenticated | 401 | `NOT_AUTHENTICATED` / `AUTHENTICATION_FAILED` |
| Not a member (regular endpoints) / not a leader (leader endpoints) | 403 | `PERMISSION_DENIED` |
| Invalid `month` | 400 | `VALIDATION_ERROR` |
| Invalid write body or photo | 400 | `VALIDATION_ERROR` |
| Unknown member id | 404 | `NOT_FOUND` |

---

## Architecture

```
MemberListAPIView / MemberBirthdaysAPIView
  -> MemberService
    -> MemberRepository (Protocol) <- MemberRepositoryImpl (ORM)
```

```
AdminMemberListAPIView / AdminMemberDetailAPIView / AdminMemberOptionsAPIView
  -> MemberRosterService
AdminMemberPhotoAPIView
  -> MemberPhotoService
AdminMemberHistoryAPIView
  -> MemberChangeLogService
      -> MemberRosterRepository (Protocol)    <- MemberRosterRepositoryImpl (ORM)
      -> MemberChangeLogRepository (Protocol) <- MemberChangeLogRepositoryImpl (ORM)
      -> MemberPhotoStorage (Protocol)        <- DefaultStorageMemberPhotoStorage
```

Pure rules in `features/members/domain/`: `member_changes.py` (history diff and text) and
`member_dates.py` (date checks). Everything wired in `config/di.py`.
