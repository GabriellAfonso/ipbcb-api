# Sunday School Domain

Sunday school (Escola Bíblica Dominical, EBD) lessons, stored as structured content, read publicly
by the Android app (Estudos → Escola Bíblica Dominical) and written by leadership from the panel.

Feature history: [`specs/026-sunday-school`](../026-sunday-school/spec.md) — decisions and their
reasons in its `research.md`.

## Data Model

### `SundaySchoolYear`

| Field | Type | Notes |
|---|---|---|
| `year` | int, unique | 2000..2100 |
| `theme` | str (≤ 200), blank | e.g. "O Drama das Escrituras"; "" = no theme |
| `created_at` / `updated_at` | datetime | automatic |

Created implicitly when a lesson is saved for a year without a row. Never created or deleted
directly through the API; the theme is edited from the panel.

### `SundaySchoolLesson`

| Field | Type | Notes |
|---|---|---|
| `year` | FK `SundaySchoolYear` (protect) | |
| `title` | str (≤ 200) | non-blank |
| `date` | date, null | day the lesson was given, when known |
| `teacher` | str (≤ 120), blank | free text, not a member link |
| `status` | `draft` \| `published` | |
| `position` | int | 0..n-1 inside the year; ties ordered by id |
| `content` | JSON | content document below, stored normalized |
| `created_by` / `updated_by` | user, null | null when the user is deleted and on imported lessons |
| `created_at` / `updated_at` | datetime | automatic |

### Content document

```json
{"sections": [{"title": "Contexto no Drama das Escrituras", "icon": "hourglass",
  "blocks": [{"type": "paragraph", "text": "O livro de Daniel está situado no período do **Exílio**…",
              "proof_texts": []}]}]}
```

- `sections` (1..30): `title` (non-blank), `icon` (icon name or null), `blocks` (1..60).
- Text fields accept `**bold**` and `*italic*` only; stored as written, rendered by the app.
- Required texts are non-blank and ≤ 5000 characters. List-like blocks hold 1..50 items.
- Optional fields are stored as `null`, `proof_texts` as `[]` when absent: the stored document is
  the validated, normalized one.

| `type` | Fields |
|---|---|
| `paragraph` | `text`, `proof_texts[]` |
| `list` | `style` (`bullet`\|`numbered`\|`roman`), `items[]`: `{text, proof_texts[]}` |
| `key_verse` | `label`?, `text`, `proof` |
| `cards` | `items[]`: `{icon?, label?, title, text?, proof_texts[]}` |
| `comparison` | `items[]` (exactly 2): `{label, title, text?, highlight}` |
| `steps` | `items[]`: `{label?, title, text?}` |
| `table` | `header[]` (1..10), `rows[][]` (1..100, each as wide as the header; cells may be blank) |
| `stats` | `items[]`: `{value (≤ 20), label}` |
| `timeline` | `events[]`: `{when (≤ 40), text}` |
| `book_facts` | `book` (Bible abbrev), `author`?, `date`?, `style`?, `reading_time`? |

A Bible reference (`proof`, each `proof_texts` item) is `{printed, reference}`, exactly the
doctrine proof-text shape: `reference` is `{book, chapter, verses: [{start, end}]}` (book = Bible
`abbrev`, `verses: []` = whole chapter) or null when the passage cannot be pinned.

**Icons** (closed list, Phosphor duotone in the app): `heart`, `scales`, `shield`, `plant`,
`hands_praying`, `crown`, `cross`, `book_open`, `scroll`, `flame`, `bird`, `church`, `hourglass`,
`sword`, `mountains`, `lightning`. Adding one changes server and app together.

**Standard sections** and their default icons (used by the import and by the app's new-lesson
template; the server applies no default):

| Section | Icon |
|---|---|
| Contexto no Drama das Escrituras | `hourglass` |
| Objetivo teológico | `crown` |
| Estrutura / Esboço | `book_open` |
| Verdades teológicas | `shield` |
| Versículos-chave | `scroll` |
| Exortação devocional | `hands_praying` |

## Endpoints

### Public (`AllowAny`, `ETag` / 304, not private)

- `GET /api/sunday-school/[?year=N]` — `{years: [{year, theme}], default_year, year: {year, theme}
  | null, lessons: [{id, title, date, teacher, position}]}`. `years` = years with at least one
  published lesson, newest first; `default_year` = the newest of them (null when none); `lessons`
  = published lessons of `year` (the default when not given), by position.
- `GET /api/sunday-school/lessons/{id}/` — `{id, title, date, teacher, position, status, year:
  {year, theme}, content, books}`, published only. `books` maps each book named by a
  `book_facts` block to `{name, position, chapters, verses}`, computed from the Bible data (the
  minimum verse count across translations).

### Panel (scope `sunday_school`, levels by method; private responses)

| Method and path | Level | Body | Success |
|---|---|---|---|
| `GET api/sunday-school/manage/lessons/?year=N` | view | — | 200 every lesson of the year (any status), by position |
| `POST api/sunday-school/manage/lessons/` | manage | `{year, title, date?, teacher?, status, content}` | 201 lesson |
| `GET api/sunday-school/manage/lessons/{id}/` | view | — | 200 lesson |
| `PATCH api/sunday-school/manage/lessons/{id}/` | manage | any subset of the create fields | 200 lesson |
| `DELETE api/sunday-school/manage/lessons/{id}/` | owner | — | 204 |
| `PUT api/sunday-school/manage/lessons/order/` | manage | `{year, lesson_ids}` | 204 |
| `GET api/sunday-school/manage/years/` | view | — | 200 `[{year, theme, lesson_count, published_count}]` |
| `PATCH api/sunday-school/manage/years/{year}/` | manage | `{theme}` | 200 year |

Full contract: [`specs/026-sunday-school/contracts/api.md`](../026-sunday-school/contracts/api.md).

## Business Rules

1. Only published lessons and years with one are ever served publicly.
2. A new lesson, or one moved to another year, goes to the end of that year; the year it left,
   and the year of a deleted lesson, are renumbered 0..n-1.
3. Reordering takes exactly the year's lessons (drafts included), each once; other years are
   untouched.
4. Content is validated on every write; then every non-null `reference` must name a Bible
   `abbrev` whose chapter and verses exist in every served translation, and every
   `book_facts.book` must be a Bible `abbrev`.
5. `created_by` / `updated_by` come from the request user, never from the body.
6. The feature never imports `features.bible`: the Bible repository exposes verse counts and book
   names as plain mappings, and `config/di.py` builds the `ScriptureIndex` from them.
7. The 2026 lessons (theme "O Drama das Escrituras", 18 lessons, published, only the official
   dates) are loaded by the data migration `sunday_school/0002_load_2026_lessons.py` from frozen
   JSON files beside it. Corrections after deploy go through the API, never by editing the files.

## Errors

| Code | Status | When |
|---|---|---|
| `SUNDAY_SCHOOL_YEAR_NOT_FOUND` | 404 | Public year without published lessons; reorder or theme of a year without row |
| `SUNDAY_SCHOOL_LESSON_NOT_FOUND` | 404 | Unknown id; draft on the public endpoint |
| `SUNDAY_SCHOOL_CONTENT_INVALID` | 400 | Content breaks the schema, an icon or a reference is invalid; body adds `errors: [{path, message}]` |
| `SUNDAY_SCHOOL_ORDER_MISMATCH` | 400 | Order not exactly the year's lessons; body adds `expected_lesson_ids` |
| `VALIDATION_ERROR` | 400 | Malformed body, unknown field, year outside 2000..2100, bad query |
