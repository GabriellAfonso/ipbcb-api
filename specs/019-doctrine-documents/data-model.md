# Data Model: Doctrine Documents

No database tables, no migration. Data lives in `server/features/doctrine/data/{slug}.json`, one
file per document, validated with Pydantic DTOs (`StrictBaseModel`, `extra="forbid"`) at startup.
The committed file is the source of truth: produced outside the repository, reviewed by a person,
and corrected by direct edits.

## Document file

```json
{
  "slug": "westminster-shorter-catechism",
  "title": "Breve Catecismo de Westminster",
  "kind": "catechism",
  "position": 1,
  "questions": [
    {
      "number": 1,
      "question": "Qual é o fim principal do homem?",
      "answer": "O fim principal do homem é glorificar a Deus, e gozá-lo para sempre.",
      "proof_texts": [
        {"printed": "1Co 10.31", "reference": {"book": "1Co", "chapter": 10, "verses": [{"start": 31, "end": 31}]}},
        {"printed": "Rm 11.36", "reference": {"book": "Rm", "chapter": 11, "verses": [{"start": 36, "end": 36}]}},
        {"printed": "Sl 86-8", "reference": null}
      ]
    }
  ]
}
```

```json
{
  "slug": "westminster-confession-of-faith",
  "title": "A Confissão de Fé de Westminster",
  "kind": "confession",
  "position": 3,
  "chapters": [
    {
      "number": 1,
      "title": "DA SAGRADAS ESCRITURAS",
      "paragraphs": [
        {"number": 1, "text": "Ainda que a luz da natureza..."},
        {
          "number": 2,
          "text": "Sob o nome de Escritura Sagrada... são os seguintes:",
          "lists": [
            {"heading": "O Velho Testamento", "items": ["Gênesis", "Êxodo", "..."]},
            {"heading": "O Novo Testamento", "items": ["Mateus", "..."]}
          ],
          "text_after": "Todos os quais foram dados por inspiração de Deus..."
        }
      ]
    }
  ]
}
```

(Example text abbreviated.) Paragraphs other than 1.2 have only `number` and `text`; `lists`
and `text_after` are omitted, not empty.

## DTOs

| DTO | Fields | Rules (checked at startup) |
|-----|--------|----------------------------|
| `VerseSpan` | `start: int`, `end: int` | `1 <= start <= end` |
| `BibleReference` | `book: str`, `chapter: int`, `verses: list[VerseSpan]` | `chapter >= 1`; empty `verses` = whole chapter |
| `ProofText` | `printed: str`, `reference: BibleReference \| None` | `printed` non-blank |
| `CatechismQuestion` | `number: int`, `question: str`, `answer: str`, `proof_texts: list[ProofText]` | texts non-blank |
| `ParagraphList` | `heading: str`, `items: list[str]` | heading non-blank; ≥1 item, items non-blank |
| `ConfessionParagraph` | `number: int`, `text: str`, `lists: list[ParagraphList] \| None = None`, `text_after: str \| None = None` | `text` non-blank; `lists`, when present, non-empty; `text_after`, when present, non-blank |
| `ConfessionChapter` | `number: int`, `title: str`, `paragraphs: list[ConfessionParagraph]` | title non-blank; paragraphs numbered 1..N |
| `CatechismDocument` | `slug`, `title`, `kind: Literal["catechism"]`, `position: int`, `questions` | questions numbered 1..N, N ≥ 1 |
| `ConfessionDocument` | `slug`, `title`, `kind: Literal["confession"]`, `position: int`, `chapters` | chapters numbered 1..N, N ≥ 1 |
| `DoctrineDocument` | `CatechismDocument \| ConfessionDocument`, discriminated by `kind` | — |
| `DoctrineDocumentSummary` | `slug`, `title`, `kind`, `item_count: int` | derived, not stored |

Cross-file rules (repository load):

- `slug` matches `^[a-z0-9]+(-[a-z0-9]+)*$` and equals the file stem.
- `position` unique across files; the list is ordered by `position`.
- Any failure → `DoctrineDataError` naming file, field path, offending value and expected shape;
  `DoctrineConfig.ready()` turns it into `ImproperlyConfigured` (research R-02).
- Counts per document and Bible references are **not** checked at startup (research R-03).

`item_count` = `len(questions)` for a catechism, `len(chapters)` for a confession.

## Rules checked only by tests on the committed files (research R-03)

| Rule | Source |
|------|--------|
| Shorter 107 questions, Larger 196, Confession 33 chapters | FR-001, FR-013 |
| Every `reference.book` is an `abbrev` in the Bible data | FR-007 |
| Every `reference` chapter exists, and every verse span fits, in every Bible version (minimum verse count across versions) | FR-010, R-04 |
| Confession 1.2 has two lists and `text_after`; no other paragraph has `lists` or `text_after` | FR-004 |

Test-only helper: `BibleVerseIndex` built from `features/bible/data/*.json` by path (no import of
`features.bible`).

## Exceptions

| Exception | Base | Where | HTTP |
|-----------|------|-------|------|
| `DoctrineDocumentNotFoundError(slug)` | `NotFoundError` | `core/domain/exceptions.py` | `404 NOT_FOUND`, `detail: "Doctrine document not found: '<slug>'"` |
| `DoctrineDataError` | `ValueError` | `features/doctrine` (startup only, never reaches HTTP) | — |
