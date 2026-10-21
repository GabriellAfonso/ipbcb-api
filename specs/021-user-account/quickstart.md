# Quickstart: User Account

## Automated

From `server/` with the Windows venv:

```powershell
..\..\..\..\.venv_windows\Scripts\python -m pytest features/accounts core -q
..\..\..\..\.venv_windows\Scripts\python -m pytest -q              # full suite at the end
..\..\..\..\.venv_windows\Scripts\python -m mypy .
..\..\..\..\.venv_windows\Scripts\python manage.py makemigrations --check --dry-run
```

`makemigrations --check` must report no changes: this feature has no migration.

## Manual (dev server)

1. Register `ana` / `secret1` (`POST api/auth/register/`), keep the pair (device A); log in again
   (device B).
2. `GET api/me/profile/` → `username: "ana"`, `has_password: true`, `date_joined: today`.
3. `POST api/me/password/` from A with a wrong `current_password` → `400 INVALID_PASSWORD`;
   with the right one → `200` and a new pair. A's old access → `401`; A's new access → `200`;
   B's access → `401`; B's refresh → `401`.
4. `POST api/me/delete/` with `{"password": "wrong"}` → `400 INVALID_PASSWORD`; with the right
   one → `204`. Login as `ana` → `401`. The profile photo file is gone from `MEDIA_ROOT`.
5. Open `http://localhost:8000/conta/excluir/`, sign in with another test account, tick the
   confirmation, submit → success page; the account no longer logs in.

## Manual step before release (Google on the web page)

Google Cloud Console → APIs & Services → Credentials → the Web OAuth client whose ID is
`GOOGLE_CLIENT_ID` → **Authorized JavaScript origins** → add `https://<production domain>`
(scheme + host only, no `/ipbcb`). Without it the Google button shows an origin error; the
username + password form keeps working.

Then put `https://<production domain>/ipbcb/conta/excluir/` in the Play Console's
"Delete account URL" field.
