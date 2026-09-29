# Quickstart: validating feature-scoped permissions

Commands run from `server/` with `.venv_windows` active (PowerShell).

## 1. Automated checks

```powershell
pytest
mypy .
ruff check .
```

Expected: all green. The tests that carry this feature:

| What | Where (planned) | Proves |
|------|-----------------|--------|
| Levels, method defaults, overrides, grant resolution | `core/tests/unit/test_access.py` | FR-001–FR-005, FR-008, FR-010, FR-030 |
| Seeded roles match the matrix on a fresh database | `core/tests/integration/test_panel_roles_seed.py` | FR-025, US1 scenario 5 |
| Every classified endpoint × {Admin, Leader, Media, none, superuser} | `core/tests/integration/test_management_access_matrix.py` | FR-013, FR-014, SC-002, SC-004 |
| Two roles give the union | same file | FR-010 |
| `is_admin` conversion | `features/accounts/tests/integration/test_is_admin_conversion_migration.py` | FR-023, FR-024 |
| Profile roles/permissions, no `is_admin` | `features/accounts/tests/integration/test_profile_api.py` | FR-019–FR-022 |
| `members/` media by role | `features/media/tests/integration/test_media_file_api.py` | FR-017, FR-018 |

## 2. Nothing still reads the old flag

```powershell
Select-String -Path (Get-ChildItem -Recurse -Include *.py) -Pattern 'is_admin|IsAdminUser|is_leader'
```

Expected: matches only in `features/accounts/migrations/0001_initial.py`, `0003_…`, `0004_…`,
the docstring of `core/migrations/0005_…`, and the tests that prove the flag is converted
(`test_is_admin_conversion_migration.py`) and gone (`test_profile_api.py`,
`test_profile_serializer.py`). Role strings (`"leader"`, `"media"`) appear in production code
only in `core/domain/access.py`; tests use them where they assert the wire format.

## 3. Migration against a restored production dump

1. Restore the latest production dump into a local PostgreSQL.
2. Before migrating, note who is admin:
   `SELECT u.username FROM accounts_profile p JOIN accounts_user u ON u.id = p.user_id WHERE p.is_admin;`
3. `python manage.py migrate`.
4. Check:
   - `SELECT name FROM auth_group ORDER BY name;` → `admin`, `leader`, `media`.
   - Members of `admin` are exactly the usernames from step 2.
   - `leader` holds 7 permissions and `media` 4, the codenames in `data-model.md`.
   - `accounts_profile` has no `is_admin` column.
5. `python manage.py migrate` again → nothing to apply, no duplicate permission rows
   (`post_migrate` get-or-create meets the seeded rows).

## 4. Manual walk-through (dev server)

1. In the Django admin, give user A the Leader role, user B the Media role; user C none.
2. Log in as each from the app (or with the API) and read `GET api/me/profile/`: compare with
   `contracts/profile-api.md`.
3. As A: edit a member → 200; delete a member → 403; `PATCH api/hymnal-history/settings/` → 403.
4. As B: `GET api/admin/members/` → 403; a `members/` photo URL → 403;
   `GET api/hymnal-history/top-hymns/` → 200.
5. Remove A's role in the Django admin; A's next management request → 403, without logging out.

## Adding a scope later

1. Add the value to `Scope`.
2. `python manage.py makemigrations core` → `AlterModelOptions` on `PanelScope`.
3. Data migration giving Leader/Media their level on it, if any (Admin needs nothing). It must
   get-or-create the new permission rows itself — `post_migrate` has not created them yet
   (research R-07).
4. Declare the scope on the new endpoints; add rows to the access-matrix test.
