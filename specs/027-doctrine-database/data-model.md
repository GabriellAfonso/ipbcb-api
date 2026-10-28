# Data Model: Doctrine Documents in the Database

## `DoctrineStandard` (table `doctrine_doctrinestandard`)

| Field | Type | Constraints | Notes |
|---|---|---|---|
| `id` | auto | PK | never exposed |
| `slug` | `SlugField(max_length=100)` | unique | stable identifier the app uses; lowercase words joined by hyphens |
| `title` | `CharField(max_length=200)` | | pt-BR, as published |
| `kind` | `CharField(max_length=10)` | choices `catechism`, `confession` | decides what `content` holds |
| `position` | `PositiveSmallIntegerField` | unique | list order |
| `edition` | `CharField(max_length=120)` | `blank=True` | source of the text, e.g. "Edição IPB"; `""` = unknown, served as `null` |
| `year` | `PositiveSmallIntegerField` | `null=True, blank=True` | year of the document, e.g. 1647 |
| `content` | `JSONField` | | `questions[]` (catechism) or `chapters[]` (confession), exactly the shape in `specs/doctrine/spec.md` |
| `created_at` | `DateTimeField(auto_now_add=True)` | | |
| `updated_at` | `DateTimeField(auto_now=True)` | | |

`Meta`: `ordering = ["position"]`, `verbose_name = "doctrine document"`,
`verbose_name_plural = "doctrine documents"`. `__str__` returns `title`.

No `status`, no `created_by` / `updated_by` (spec FR-003).

### Validation

Rows are written only by data migrations, through `load_doctrine_documents()`:

- the document matches `CatechismDocument` or `ConfessionDocument` (strict, discriminated by
  `kind`; non-blank texts; verse spans ordered);
- questions, chapters and each chapter's paragraphs are numbered `1..N` without gaps;
- slug matches `[a-z0-9]+(-[a-z0-9]+)*` and equals the file name;
- `position` is unique across the files of the migration.

Rows are read back through the same DTOs (`DoctrineRepositoryImpl._to_document`).

### Mapping row ⇄ DTO

```
row → {"slug", "title", "kind", "position",
       "edition": row.edition or None, "year": row.year,
       "questions" | "chapters": row.content}  → DoctrineDocument (validated)
```

## DTO changes (`features/doctrine/dtos.py`)

- `CatechismDocument`, `ConfessionDocument`: `edition: str | None = None`, `year: int | None = None`.
- `DoctrineDocumentSummary`: same two fields, set from the document by the service.

## Initial rows (migration `0002_load_westminster_standards`)

| position | slug | kind | items |
|---|---|---|---|
| 1 | `westminster-shorter-catechism` | catechism | 107 questions |
| 2 | `westminster-larger-catechism` | catechism | 196 questions |
| 3 | `westminster-confession-of-faith` | confession | 33 chapters |

`edition` "" and `year` null on all three.
