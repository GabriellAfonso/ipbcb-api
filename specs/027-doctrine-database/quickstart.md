# Quickstart: Doctrine Documents in the Database

All commands from `server/` with `.venv_windows` active.

## 1. Domain tests

```powershell
python -m pytest features/doctrine -q
```

Expect: committed-data checks (107 / 196 / 33, Confession 1.2, references in every Bible version,
only LC Q153/Q163 null), load-migration forward/reverse, repository round trip, API responses,
`ETag`/`304`, `404`, `405`, admin without doctrine.

## 2. Migration on a real database

```powershell
python manage.py migrate doctrine
python manage.py shell -c "from features.doctrine.models import DoctrineStandard as D; print(list(D.objects.values_list('position', 'slug')))"
```

Expect `[(1, 'westminster-shorter-catechism'), (2, 'westminster-larger-catechism'), (3, 'westminster-confession-of-faith')]`.

Rollback check:

```powershell
python manage.py migrate doctrine 0001
python manage.py migrate doctrine
```

The rows disappear after the first command and come back after the second.

## 3. API

```powershell
python manage.py runserver
curl http://localhost:8000/api/doctrine/
curl -i http://localhost:8000/api/doctrine/westminster-confession-of-faith/
```

Expect the [contract](contracts/doctrine-api.md): same bodies as before plus `edition`/`year`
`null`; send the `ETag` back in `If-None-Match` and get `304`.

## 4. Full suite and hooks

```powershell
python -m pytest -q
pre-commit run --all-files
```
