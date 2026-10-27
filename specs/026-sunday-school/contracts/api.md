# API Contract: Sunday School

Errors are `{"error_code", "detail"}` (spec 001); `detail` in pt-BR.

## Public (`AllowAny`, `ETag` / `If-None-Match` → 304)

### `GET api/sunday-school/` — operation `sunday_school_index`

Query: `year` (optional int). Absent = default year.

```json
{
  "years": [{"year": 2026, "theme": "O Drama das Escrituras"}],
  "default_year": 2026,
  "year": {"year": 2026, "theme": "O Drama das Escrituras"},
  "lessons": [
    {"id": 1, "title": "Panorama de Josué", "date": null, "teacher": "", "position": 0}
  ]
}
```

No published lesson at all: `{"years": [], "default_year": null, "year": null, "lessons": []}`.
`year` given but not published: 404 `SUNDAY_SCHOOL_YEAR_NOT_FOUND`. Malformed `year`: 400
`VALIDATION_ERROR`.

### `GET api/sunday-school/lessons/<id>/` — operation `sunday_school_lesson`

```json
{
  "id": 11, "title": "Panorama de Daniel", "date": "2026-08-16", "teacher": "", "position": 10,
  "status": "published",
  "year": {"year": 2026, "theme": "O Drama das Escrituras"},
  "content": {"sections": [{"title": "Contexto no Drama das Escrituras", "icon": "hourglass",
    "blocks": [{"type": "paragraph", "text": "O livro de Daniel…", "proof_texts": []}]}]},
  "books": {}
}
```

`books` has one entry per book named by a `book_facts` block:
`"Mc": {"name": "Marcos", "position": 41, "chapters": 16, "verses": 678}`.
Draft or unknown: 404 `SUNDAY_SCHOOL_LESSON_NOT_FOUND`.

## Panel (scope `sunday_school`; `IsAuthenticated`; responses `private`)

| Method and path | Operation | Level | Body | Success |
|---|---|---|---|---|
| `GET api/sunday-school/manage/lessons/?year=2026` | `sunday_school_manage_lessons_list` | view | — | 200 `[lesson]` (full, drafts included, by position); unknown year → `[]` |
| `POST api/sunday-school/manage/lessons/` | `sunday_school_manage_lessons_create` | manage | `{year, title, date?, teacher?, status, content}` | 201 lesson |
| `GET api/sunday-school/manage/lessons/<id>/` | `sunday_school_manage_lessons_retrieve` | view | — | 200 lesson |
| `PATCH api/sunday-school/manage/lessons/<id>/` | `sunday_school_manage_lessons_partial_update` | manage | subset of create fields | 200 lesson |
| `DELETE api/sunday-school/manage/lessons/<id>/` | `sunday_school_manage_lessons_destroy` | owner | — | 204 |
| `PUT api/sunday-school/manage/lessons/order/` | `sunday_school_manage_lessons_order` | manage | `{year, lesson_ids}` | 204 |
| `GET api/sunday-school/manage/years/` | `sunday_school_manage_years_list` | view | — | 200 `[{year, theme, lesson_count, published_count}]` newest first |
| `PATCH api/sunday-school/manage/years/<year>/` | `sunday_school_manage_years_partial_update` | manage | `{theme}` | 200 year (admin shape) |

Lesson (panel) = public lesson shape, any status.

## Errors

| Code | Status | When |
|---|---|---|
| `SUNDAY_SCHOOL_YEAR_NOT_FOUND` | 404 | Public year not published; reorder/theme of a year without row |
| `SUNDAY_SCHOOL_LESSON_NOT_FOUND` | 404 | Unknown id; draft on the public endpoint |
| `SUNDAY_SCHOOL_CONTENT_INVALID` | 400 | Schema, icon, Bible reference or `book_facts.book` invalid; body adds `errors: [{path, message}]` |
| `SUNDAY_SCHOOL_ORDER_MISMATCH` | 400 | Order not exactly the year's lessons; body adds `expected_lesson_ids` |
| `VALIDATION_ERROR` | 400 | Malformed body, unknown field, year out of 2000..2100, bad query |
| `NOT_AUTHENTICATED` / `PERMISSION_DENIED` | 401 / 403 | Panel without token / without level |
