# Quickstart: Rota Reminders by Push

From `server/`, with `.venv_windows` active.

## 1. Migrate

```powershell
python manage.py makemigrations schedule   # expect 0004 with ScheduleReminderClaim only
python manage.py migrate
```

## 2. Tests

```powershell
pytest features/schedule core -q
```

Expected: rules (windows, slots JSON), service (each kind once, gating by overwrite window,
missed occasions not sent next day, provider failure still claims), repository (claim race via
`run_id`, entry and month queries, recipients with/without member access), command output.

## 3. Manual run

```powershell
python manage.py send_schedule_reminders -v 2
```

Prints one line per kind, e.g. `kind=schedule_eve occasion=2026-10-29 members=2 devices=3 sent=3`.
Without push credentials the pushes are logged as `push_disabled` and the claims are still written.

## 4. Scenario check (dev DB)

1. Link a test user's profile to a member and give it member access; register a device token.
2. Save a rota for the current month with that member on tomorrow's service; backdate the month's
   `created_at` by 31 minutes in the Django shell.
3. Run the command after 19:00: one `schedule_published` (if the moment was today) and one
   `schedule_eve`. Run again: nothing new.
