# Quickstart: validating Members Management

Contract: [contracts/admin-members-api.md](contracts/admin-members-api.md). Rules:
[data-model.md](data-model.md).

## Prerequisites

- Windows venv `.venv_windows` active, run from `server/`.
- Migrations applied: `python manage.py migrate`.
- Feature 009 in place (`members` folder rule = leaders).

## 1. Automated checks

```bash
cd server
python -m pytest features/members core -q
python -m mypy .
cd .. && pre-commit run --all-files && cd server   # ruff, ruff-format, bandit, mypy
python manage.py makemigrations --check --dry-run   # no pending model changes
```

Expected: all green; the members suite covers every scenario below.

## 2. Manual run (local, DEBUG)

Create a leader and a plain member (Django shell or admin): user A with `profile.is_admin=True`,
user B with `profile.is_member=True`. Get tokens via `POST /api/auth/login/`. Seed a status,
a role and two ministries in the admin.

| Step | Request | Expect |
|---|---|---|
| 1 | B `GET /api/admin/members/` | 403 `PERMISSION_DENIED` |
| 2 | A `GET /api/admin/members/options/` | 200, three lists by name |
| 3 | A `POST /api/admin/members/` `{"name": "Teste"}` | 201, `is_active: true` |
| 4 | A `GET /api/admin/members/{id}/history/` | one `created` row, editor = A |
| 5 | A `PATCH` `{"status_id": <s>, "ministry_ids": [<m1>, <m2>]}` | 200; history +2 rows |
| 6 | A `PATCH` same body again | 200; history unchanged |
| 7 | A `PATCH` `{"birth_date": "2999-01-01"}` | 400, message has the date; history unchanged |
| 8 | A `PUT .../photo/` with a JPEG | 200, `photo_url` under `members/`, no name in path; file on disk |
| 9 | B `GET <photo_url>` | 403 |
| 10 | A `PUT .../photo/` with a PNG | old file gone, new present; history "photo changed" ×2 |
| 11 | A `PUT .../photo/` with a `.png`-named text file | 400; current photo intact |
| 12 | A `PATCH` `{"is_active": false}`; B `GET /api/members/` | member absent from regular list; present in leader list |
| 13 | A `GET /api/admin/members/{id}/` twice with `If-None-Match` | second is 304; headers `private, no-store`, `Vary: Authorization` |
| 14 | A `DELETE /api/admin/members/{id}/` | 204; row, history rows and file all gone |

## 3. Log check

During steps 3–14, every `member_*` log line carries `member_id`, `editor_id`,
`changed_fields` and nothing else from the member (no name, dates, status, path).
