# Contract Changes: Leader Members API and Birthdays

Only the fields that change. Everything else (auth, caching, errors, other routes) is as in
`specs/010-members-management/contracts/admin-members-api.md`.

## MemberRecord (GET/POST/PATCH responses)

`birth_date` is gone. Three nullable integers take its place:

```json
{
  "id": 12,
  "name": "Ana Souza",
  "first_name": "Ana",
  "last_name": "Souza",
  "birth_day": 2,
  "birth_month": 4,
  "birth_year": null,
  "gender": "F",
  "status": {"id": 1, "name": "Comungante"},
  "role": null,
  "ministries": [],
  "baptism_date": "2005-06-12",
  "is_active": true,
  "photo_url": null,
  "created_at": "2026-09-25T14:02:11Z"
}
```

## POST `api/admin/members/` and PATCH `api/admin/members/{id}/`

Body accepts `birth_day`, `birth_month`, `birth_year` (integer or `null`), each optional.
On PATCH, a part not sent keeps its stored value; `null` clears it. Sending `birth_date` is
rejected as an unknown key:

```json
{"error_code": "VALIDATION_ERROR",
 "detail": "Campos não aceitos: ['birth_date']. Aceitos: [...]."}
```

400 `VALIDATION_ERROR` for any rule in `data-model.md`, Validation rules. Examples of `detail`:

| Body (merged with stored record) | `detail` names |
|---|---|
| `{"birth_day": 12}` on a member with no month | `birth_day=12, birth_month=None`, "envie os dois ou nenhum" |
| `{"birth_day": 31, "birth_month": 4}` | `31/04`, the last valid day of the month |
| `{"birth_day": 29, "birth_month": 2, "birth_year": 1990}` | `29/02/1990`, year is not a leap year |
| `{"birth_year": 2027}` | `2027`, up to the current year |
| `{"birth_year": 1990, "baptism_date": "1989-05-01"}` | `1989-05-01` and `1990` |

## Leader list `GET api/admin/members/`

Unchanged (it never carried a birth date).

## History `GET api/admin/members/{id}/history/`

Shape unchanged. New `field` values:

```json
{"field": "birth_year", "old_value": "1990", "new_value": "1991", ...}
```

Older rows with `"field": "birth_date"` and `YYYY-MM-DD` values keep being returned.

## Birthdays `GET api/members/birthdays/?month=M[-M]`

Response shape unchanged:

```json
{"birthdays": [{"name": "Ana Souza", "gender": "F", "birth_month": 4, "birth_day": 2}]}
```

Now includes only members with both `birth_day` and `birth_month`; members with only a year or
nothing are absent. A 29/02 birthday is returned as day 29 in every year.
