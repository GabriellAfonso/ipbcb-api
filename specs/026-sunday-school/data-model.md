# Data Model: Sunday School Lessons

## `SundaySchoolYear` (`sunday_school_sundayschoolyear`)

| Field | Type | Rules |
|---|---|---|
| `id` | auto | |
| `year` | `PositiveSmallIntegerField`, unique | 2000..2100 (checked by DTOs) |
| `theme` | `CharField(200)`, blank | "" when the year has no theme |
| `created_at` / `updated_at` | `DateTimeField` | auto |

`Meta.ordering = ["-year"]`; `__str__` → `"2026"` or `"2026 — O Drama das Escrituras"`.

Created by the repository with `get_or_create(year=…)` whenever a lesson is saved for it. Never
deleted by the API.

## `SundaySchoolLesson` (`sunday_school_sundayschoollesson`)

| Field | Type | Rules |
|---|---|---|
| `id` | auto | |
| `year` | FK `SundaySchoolYear`, `PROTECT`, `related_name="lessons"` | required |
| `title` | `CharField(200)` | non-blank |
| `date` | `DateField`, null | |
| `teacher` | `CharField(120)`, blank | free text |
| `status` | `CharField(10)` choices `draft`/`published` | |
| `position` | `PositiveIntegerField` | 0..n-1 inside the year; ties ordered by id |
| `content` | `JSONField` | normalized `LessonContent` dump |
| `created_by` / `updated_by` | FK user, null, `SET_NULL`, `related_name="+"` | |
| `created_at` / `updated_at` | `DateTimeField` | auto |

`Meta.ordering = ["year__year", "position", "id"]`; index `(year, status, position)`;
`__str__` → title.

## Content document (`content_schema.py`, stored in `content`)

```text
LessonContent      sections: list[Section] (1..30)
Section            title: text, icon: LessonIcon | None, blocks: list[Block] (1..60)
Block              discriminated on "type":
  ParagraphBlock   text, proof_texts: list[ProofText] = []
  ListBlock        style: bullet|numbered|roman, items: list[ListItem] (1..50)
    ListItem       text, proof_texts = []
  KeyVerseBlock    label: text | None, text, proof: ProofText
  CardsBlock       items: list[Card] (1..50)
    Card           icon | None, label | None, title, text | None, proof_texts = []
  ComparisonBlock  items: list[ComparisonItem] (exactly 2)
    ComparisonItem label, title, text | None, highlight: bool
  StepsBlock       items: list[Step] (1..50)
    Step           label | None, title, text | None
  TableBlock       header: list[text] (1..10), rows: list[list[str]] (1..100), each row len == header
  StatsBlock       items: list[Stat] (1..50)
    Stat           value (≤ 20 chars), label
  TimelineBlock    events: list[TimelineEvent] (1..50)
    TimelineEvent  when (≤ 40 chars), text
  BookFactsBlock   book (abbrev), author | None, date | None, style | None, reading_time | None
ProofText          printed: text, reference: BibleReference | None
BibleReference     book: str, chapter: int ≥ 1, verses: list[VerseSpan]
VerseSpan          start, end with 1 ≤ start ≤ end
```

"text" = non-blank string ≤ 5000 chars; stored as given (no strip). Table cells may be blank.

Checks after the schema (`ScriptureIndex`): every non-null `reference` names a known book, an
existing chapter and verses ≤ that chapter's count in every translation; every `book_facts.book`
is a known book.

## DTOs (`dtos.py`)

- `LessonCreateDTO`: `year` (2000..2100), `title`, `date?`, `teacher` = "", `status`,
  `content: dict[str, object]`.
- `LessonPatchDTO`: same fields all optional; applied by `model_fields_set`; `title`, `year`,
  `status`, `content` cannot be null; `date` null clears it.
- `LessonOrderDTO`: `year`, `lesson_ids: list[int]` (≤ 500).
- `YearThemeDTO`: `theme` (≤ 200, may be blank).
- `LessonSummaryDTO`: `id, title, date, teacher, position` (+ `status` in the panel variant).
- `LessonDTO`: summary fields + `status`, `year: YearDTO`, `content`, `books: dict[str, BookFactsDTO]`.
- `YearDTO`: `year, theme`; `YearAdminDTO`: + `lesson_count`, `published_count`.
- `SundaySchoolIndexDTO`: `years: list[YearDTO]`, `default_year: int | None`,
  `year: YearDTO | None`, `lessons: list[LessonSummaryDTO]`.
- `BookFactsDTO`: `name, position, chapters, verses`.

## State

`draft` ⇄ `published` freely through PATCH. A lesson counts publicly only while `published`; a
year is public while it has one.
