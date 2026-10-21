# Quickstart: Member Access and Access Requests

From `server/` with the project virtualenv.

## Tests

```bash
python -m pytest features/accounts features/members core -q
python -m pytest -q                       # full suite
python -m mypy .
python manage.py makemigrations --check --dry-run
```

## Manual check (dev server)

1. Account A without access: `POST api/me/access-requests/ {"type": "access"}` → 201;
   `GET api/me/profile/` → `access_status: "pending"`; repeat → 409 `ACCESS_REQUEST_PENDING`.
2. As Liderança: `GET api/admin/profiles/?status=pending` lists A;
   `POST api/admin/profiles/requests/{id}/approve/` → A's `member_access: true`; A's device gets
   `access_request_approved`.
3. As Mídia: any `api/admin/profiles/…` → 403.
4. Liderança account with the flag off: `GET api/schedule/…` → 200 (was 403).
5. Link A to a member: `PATCH api/admin/profiles/{A}/ {"member_id": 12}`; as A,
   `GET api/me/member/` → roll data with `Cache-Control: private, no-store` and no `ETag`.

## Migration controls (constitution §5, `RenameField`)

Before deploy, on a restored production dump:

```bash
python manage.py migrate                         # applies accounts 0006/0007, core 0009/0010
# check: count of profiles with member_access = true equals the count with is_member = true before
python manage.py migrate accounts 0005           # rollback: column is is_member again, same values
python manage.py migrate core 0008
python manage.py migrate                         # forward again
```

Record the result in `tasks.md` (verification task).
