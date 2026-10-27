# Quickstart: Sunday School

Validation guide. Commands from `server/` with `.venv_windows` active.

1. `python manage.py migrate` on an empty database → year 2026 ("O Drama das Escrituras") and 18
   published lessons (`python manage.py shell -c "from features.sunday_school.models import *;
   print(SundaySchoolLesson.objects.count())"` → 18).
2. `pytest features/sunday_school core/tests` → green; includes the committed-lessons test (every
   reference exists in every translation, 18 files, 9 dates).
3. `GET /api/sunday-school/` without a token → 2026 default, 18 summaries by position; repeat with
   `If-None-Match` → 304.
4. As Liderança: `POST /api/sunday-school/manage/lessons/` a 2026 draft → absent from step 3;
   `PUT …/order/` placing it first → positions shift; `PATCH` `status: published` → visible.
5. As Mídia: any panel call → 403.
6. `python manage.py migrate sunday_school 0001` → the 2026 rows are gone (rollback runs).
7. `pre-commit run --all-files` → clean.

Contract details: [contracts/api.md](contracts/api.md). Model: [data-model.md](data-model.md).
