# Quickstart: Validate the Birth Date Split

Commands run from `server/` with `.venv_windows` active (PowerShell).

## §1 Tests and static checks

```powershell
pytest features/members
mypy .
ruff check .
```

Expected: all green. Coverage to look for (names indicative):

- `tests/unit/test_member_dates.py` — every row of `data-model.md`, Validation rules, rejected
  and accepted, each asserting the offending value is in the message.
- `tests/unit/test_member_changes.py` — one history row per changed part, numbers as text.
- `tests/unit/test_member_roster_service.py` — patch sending only `birth_day` is checked
  against the stored month.
- `tests/integration/test_birth_date_split_migration.py` — the three conversion cases, and
  `migrate members 0004` refusing with `IrreversibleError`.
- `tests/integration/test_member_constraints.py` — database refuses day without month and
  out-of-range values.
- `tests/integration/test_birthdays_api.py` — year-only and empty members absent; shape
  unchanged; order month, day.
- `tests/integration/test_admin_members_api.py` — `birth_date` key rejected; three fields in
  and out.

## §2 Conversion against a restored production dump (before the deploy)

1. Restore the dump into a local PostgreSQL and point `.env` at it.
2. Before migrating, keep the original values:
   ```sql
   CREATE TABLE _birth_before AS SELECT id, birth_date FROM members_member;
   ```
3. Run `python manage.py migrate members 0005` (stop before the column is removed).
4. This query must return **zero rows**:
   ```sql
   SELECT m.id
   FROM members_member m JOIN _birth_before b ON b.id = m.id
   WHERE (b.birth_date IS NULL
          AND (m.birth_day IS NOT NULL OR m.birth_month IS NOT NULL OR m.birth_year IS NOT NULL))
      OR (b.birth_date IS NOT NULL
          AND (m.birth_day   IS DISTINCT FROM EXTRACT(DAY   FROM b.birth_date)
            OR m.birth_month IS DISTINCT FROM EXTRACT(MONTH FROM b.birth_date)
            OR m.birth_year  IS DISTINCT FROM
               NULLIF(EXTRACT(YEAR FROM b.birth_date), 1)));
   ```
5. Count check — the number of year-0001 rows before equals the number of day+month-only rows
   after:
   ```sql
   SELECT (SELECT count(*) FROM _birth_before WHERE EXTRACT(YEAR FROM birth_date) = 1),
          (SELECT count(*) FROM members_member
            WHERE birth_day IS NOT NULL AND birth_year IS NULL);
   ```
6. `python manage.py migrate members` (removes `birth_date`), then `DROP TABLE _birth_before;`.

## §3 API smoke test (local, seeded)

```powershell
python manage.py seed_birthdays
```

As a leader:

- `PATCH /ipbcb/api/admin/members/{id}/` with `{"birth_year": null}` → record keeps day and
  month, `birth_year: null`; history has one `birth_year` row.
- `PATCH` with `{"birth_month": null}` on a member with a day → 400 naming `birth_day`.
- `POST` with `{"name": "X", "birth_date": "1990-01-01"}` → 400 unknown key.

As a member:

- `GET /ipbcb/api/members/birthdays/?month=1-12` → the year-only and empty seeded members are
  absent; the day+month-only one is present.
