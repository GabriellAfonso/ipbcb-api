# Quickstart: validating the Sunday setlist feature

Run from `server/` with `.venv_windows` active (memory: running tests). Shapes in
[contracts/](contracts/), entities in [data-model.md](data-model.md).

## 1. Automated checks

```powershell
python -m pytest features/songs core features/accounts -q
python -m mypy .
ruff check .
python manage.py makemigrations --check --dry-run   # nothing pending after 0008 / core 0007
```

Whole suite at the end of the feature: `python -m pytest -q`.

Expected coverage, by story (fakes named in `core/tests/fakes.py` and `features/songs/tests/fakes.py`:
`FakePushSender`, `FakeDeviceTokenRepository`, `FakeWorshipMembership`, `FakeSetlistRepository`,
`FrozenClock`):

| Story | Proven by |
|-------|-----------|
| US1 save/replace/validation | `test_setlist_rules.py`, `test_setlist_service.py`, `test_setlist_api.py` (403 ×2, 400 ×4, 404, replace) |
| US2 distribution | `test_push_service.py` (invalid tokens deleted, abort on transport error, disabled), `test_fcm_push_sender.py` (fake HTTP session: 200, 404 `UNREGISTERED`, 400 `INVALID_ARGUMENT` kept, timeout aborts), `test_setlist_api.py` (push recipients; save succeeds when sender raises), current read |
| US3 devices | `test_device_api.py` (register, move between users, unregister own/other/unknown, 401) |
| US4 flags | `test_profile_api.py` (four role × ministry combinations, ETag changes) |
| US5 reminder | `test_reminder_slot.py` (20:59, 21:00, 21:29, 21:30, 23:59, Saturday), `test_setlist_reminder_service.py` (spec scenario: sends at 21:05, 21:35, 22:01 only; restart; plays registered; missed windows; provider failure still claims) |
| US6 pending/by date | `test_setlist_api.py` (pending order, future excluded, cleared by plays, 404 by date) |
| R-04 recipients query | `test_access_repository.py` (Admin, Leader via codename, Media excluded, inactive excluded) |
| R-03 membership query | `test_worship_repository.py` (case/whitespace variants, unlinked profile, inactive user) |

## 2. Local end-to-end without Firebase

`FCM_SERVICE_ACCOUNT_JSON_BASE64` empty → pushes disabled, everything else works.

1. Django admin: create ministry "Louvor"; link a test user's profile to a member in it; put the
   user in the Liderança group.
2. `GET api/me/profile/` → `is_worship_member: true`, `can_save_setlist: true`.
3. `POST api/me/devices/` with `{"token": "local-test"}` → `204`.
4. `PUT api/setlists/2026-10-04/` with two items → `200`; server log shows `push_disabled`
   with `devices: 1`.
5. Same with `2026-10-05` → `400` naming Monday.
6. `GET api/setlists/current/` → the 04/10 setlist.
7. `GET api/setlists/pending-confirmation/` → empty until 04/10 has passed.

## 3. Reminder by hand

```powershell
python manage.py send_setlist_reminders -v 2
```

Outside Sunday 21:00–24:00 it prints `outcome=outside_window` (only with `-v 2`; at the default
verbosity that outcome is silent, so the minute loop does not flood the container log). To exercise windows without
waiting for Sunday, use the service tests (fixed clock); there is no time override flag on the
command by design.

## 4. Real FCM (staging or production, once)

1. Firebase console → service account key for the app's project → `base64 -w0 key.json` → put
   the line in `.env` as `FCM_SERVICE_ACCOUNT_JSON_BASE64`. Delete `key.json`.
2. `docker compose -f compose.prod.yml up -d ipbcb_server ipbcb_setlist_reminder`.
3. Log in on a phone in the worship ministry; save a setlist; the phone receives
   `setlist_saved` within a minute (SC-001).
4. Measure save latency with the full worship ministry's devices registered: must stay under
   3 s (SC-002, R-07). Then block egress to `fcm.googleapis.com` (or set a wrong project) and
   save again: still `200`, under 3 s, log `push_transport_error`.
5. Uninstall the app on a test phone; save again; log shows `invalid_removed: 1`; the token row
   is gone.
6. On a Sunday with a setlist and no plays, watch `ipbcb-setlist-reminder-prod` logs from 21:00:
   one `sent` per half hour; register plays; the next run logs `confirmed`.

## 5. Migrations against a production dump

Both migrations are generated `CreateModel`s; still run `migrate` and
`migrate songs 0007 && migrate core 0006` (rollback) on a restored dump before deploying.
