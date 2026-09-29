# Quickstart: validating member tags in gallery photos

Commands run from `server/` with `.venv_windows` active (PowerShell). Contract details in
[contracts/gallery-tags-api.md](contracts/gallery-tags-api.md); fields in
[data-model.md](data-model.md); decisions in [research.md](research.md).

## 1. Automated checks

```powershell
pytest
mypy .
ruff check .
```

Expected: all green. The tests that carry this feature (planned locations):

| What | Where | Proves |
|------|-------|--------|
| `normalise_bulk` (dedupe, empty, overlap, limit 200), `replace_diff`, `bulk_diff` | `features/gallery/tests/unit/test_tag_rules.py` | FR-014, FR-016–FR-019 |
| Tag service with fakes: replace, bulk, no-op writes change nothing, offending ids collected in one error, FK race mapped to the same error, log line only on change | `features/gallery/tests/unit/test_photo_tag_service.py` | FR-013–FR-019, FR-036 |
| `require_int_list` (ints, repeated, `abc`, `1.5`, empty string) | `core/tests/unit/test_parsing_guards.py` | FR-023 |
| Tag repository: current tags, write diff bumps only changed photos, `tagged_members` skips trashed photos, rename check, delete bump | `features/gallery/tests/integration/test_photo_tag_repository.py` | FR-009, FR-012, FR-026–FR-028 |
| `MemberDirectory` on `MemberRepositoryImpl`: every member incl. inactive, by name then id; `existing_ids` | `features/members/tests/integration/test_member_repository.py` | FR-008, FR-020 |
| **Regression**: AND filter with two members (P1 only), on `/api/photos/` and on an album (sub-album photo excluded) | `features/gallery/tests/integration/test_photo_tags_api.py` | FR-022, US2-2, US2-4 |
| **Regression**: bulk add/remove keeps every other tag | `test_photo_tags_api.py` | FR-014, US4-1 |
| **Regression**: atomic failure (unknown photo + trashed photo + unknown member → one `404` listing all, no tag changed) | `test_photo_tags_api.py` | FR-015, US4-3 |
| **Regression**: tags hidden with a trashed photo (filter, tagged-member list, counts) and back on restore | `test_photo_tags_api.py` | FR-009, FR-012, US2-7/8 |
| **Regression**: picker entries have exactly `{"id", "name"}`, inactive members included | `test_photo_tags_api.py` | FR-020, US6-1 |
| **Regression**: Mídia reaches the picker (`200`) but `GET /api/members/` stays `403` (not a member) | `features/gallery/tests/integration/test_gallery_access.py` | FR-031, US6-2 |
| **Regression**: feed reports a renamed tagged member's photos (API and Django admin), and a deleted one's | `features/gallery/tests/integration/test_change_feed_api.py` | FR-026, US5-2/3/4 |
| Feed ignores a rename of an untagged member and a change to another field | `test_change_feed_api.py` | FR-027 |
| Photo resource keeps every older field; `members` last | `features/gallery/tests/integration/test_gallery_legacy_reads.py` | FR-011, SC-006 |
| Profile: `member_id` null / set; `PATCH` ignores it; unlinked after member deletion; second link refused by the admin form | `features/accounts/tests/integration/test_profile_member_link.py` | FR-001–FR-006 |
| Admin: photo page shows tags read-only; profile form has the member autocomplete; member delete works with tags | `features/gallery/tests/integration/test_gallery_admin.py`, `features/accounts/tests/integration/test_profile_member_link.py` | FR-002, FR-029 |
| Both migrations roll back and forward (table and column) | `features/gallery/tests/integration/test_member_tag_migrations.py` | R-12 |
| Purge removes tags with the photo | `features/gallery/tests/integration/test_purge_gallery_trash.py` | FR-009 |
| Every new endpoint × {Admin, Liderança, Mídia, member without role, non-member} | `test_gallery_access.py`, `core/tests/integration/test_management_access_matrix.py` | FR-030, FR-043 |
| No import of `features.members` from `features.gallery` or `features.accounts` (a test that scans the source for the import) | `features/gallery/tests/integration/test_feature_boundaries.py` | constitution |

## 2. Old app compatibility

```powershell
pytest features/gallery/tests/integration/test_gallery_legacy_reads.py
```

Expected: every Photo field returned before 015 is still there with the same meaning; `members`
is added last. The profile keeps its five fields and adds `member_id`.

## 3. Migrations against a restored production dump

1. Restore the latest production dump into a local PostgreSQL. Record the counts of
   `gallery_photo`, `accounts_profile` and `members_member`.
2. `python manage.py migrate` → `gallery 0005` and `accounts 0005` apply.
3. Check: counts unchanged; `gallery_phototag` exists and is empty, with `unique_photo_tag`;
   `accounts_profile.member_id` exists, every value `NULL`, with a unique index.
4. Roll back and prove it: `python manage.py migrate gallery 0004` and
   `python manage.py migrate accounts 0004` → table and column gone, counts unchanged. Migrate
   forward again → same state as step 3.
5. `EXPLAIN` the AND filter for two member ids → one join on `gallery_phototag` using the member
   index, not a scan per member.

## 4. Manual walk-through (dev server, `DEBUG=True`)

1. Django admin: open a profile, search "Mar" in the member field, link it to member A. Link a
   second profile to A → form error, nothing saved.
2. As that user: `GET /accounts/api/me/profile/` → `member_id` = A.
3. As Mídia: `GET /api/gallery/taggable-members/` → ids and names only.
   `PUT /api/photos/{P1}/members/` with `[A, B]` → `200`, `members` lists both.
   `POST /api/photos/members/` with `photo_ids [P1, P2]`, `add [C]`, `remove [B]` → P1 `[A, C]`,
   P2 `[C]`.
4. As a member: `GET /api/gallery/changes/` → keep the cursor.
   `GET /api/gallery/tagged-members/` → A (1), C (2).
   `GET /api/photos/?member_id=A&member_id=C` → P1 only. `?member_id=abc` → `400`.
5. Django admin: rename C. As the member: `GET /api/gallery/changes/?since=<cursor>` → P1 and P2
   with the new name.
6. As Mídia: `DELETE /api/photos/{P2}/`. As the member: the tagged-member list shows C with 1;
   the filter by C returns P1 only.
7. As Mídia: `GET /api/members/` → `403` (Mídia not flagged a member).
8. Django admin: the photo page of P1 lists A and C, with no way to edit them.

## 5. Deploy

Backend only; migrations run at container start (`compose.prod.yml`). No cron or nginx change.
Then, in the Django admin, link the profiles of the people who want "photos of me". Old app
versions keep working: they ignore `members` and `member_id`.
