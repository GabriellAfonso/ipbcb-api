# Quickstart: validating Doctrine Documents

Run everything from `server/` with the Windows venv active (`.venv_windows`). Commands are
PowerShell. The three JSON files in `features/doctrine/data/` are produced outside the repository
and reviewed by a person; nothing here generates them.

## 1. Tests

```powershell
python -m pytest features/doctrine
```

Covers: every startup rule in [data-model.md](data-model.md) (one broken fixture per rule), the
committed files (107 / 196 / 33, contiguous numbering, Confession 1.2 shape, Bible-domain book
abbreviations, verse existence in every Bible version), and the API contract in
[contracts/doctrine-api.md](contracts/doctrine-api.md).

At the end of the feature, the full suite: `python -m pytest`.

## 2. API by hand

```powershell
python manage.py runserver
curl.exe -s http://localhost:8000/api/doctrine/
curl.exe -si http://localhost:8000/api/doctrine/westminster-shorter-catechism/ | Select-Object -First 12
```

- List: three entries, order Shorter, Larger, Confession; counts 107, 196, 33.
- Document: `ETag` header present. Repeat with `-H 'If-None-Match: <tag>'` → `304`, empty body.
- `curl.exe -si http://localhost:8000/api/doctrine/Westminster-Shorter-Catechism/` → `404`,
  `error_code: NOT_FOUND`.

## 3. Startup guard

Renumber question 5 to 6 in a data file, then `python manage.py check` → fails with
`ImproperlyConfigured` naming the file, `questions[4].number`, the value `6` and the expected `5`.
Revert with `git checkout -- features/doctrine/data`.

## 4. Text correction reaches the phone

Change one character in an answer, restart, request with the old `ETag` → `200` and a new `ETag`.
Revert.
