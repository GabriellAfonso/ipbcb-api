# Doctrine Domain

Read-only domain that serves the Westminster Standards (Shorter Catechism, Larger Catechism,
Confession of Faith) as structured data. No authentication required — fully public.

Feature history: [`specs/019-doctrine-documents`](../019-doctrine-documents/spec.md),
[`specs/027-doctrine-database`](../027-doctrine-database/spec.md) (files moved to the database).

## Overview

The Android app shows these documents in Estudos → Doutrina and keeps an offline snapshot,
revalidated with `ETag`. Data is served, not a PDF, so the app decides the presentation and can
make Bible references tappable (opening the Bible tab).

## Data Model

One table, `DoctrineStandard`, one row per document:

| Field | Type | Notes |
|-------|------|-------|
| `slug` | slug, unique | stable identifier used by the app |
| `title` | str | pt-BR, as published |
| `kind` | `catechism` \| `confession` | decides what `content` holds |
| `position` | int, unique | list order |
| `edition` | str, blank | where the text comes from, e.g. "Edição IPB"; empty = unknown, served as `null` |
| `year` | int, nullable | year of the document, e.g. 1647 |
| `content` | JSON | the `questions` (catechism) or `chapters` (confession) list below, exactly that shape |
| `created_at` / `updated_at` | datetime | automatic |

No status and no author: nobody edits doctrine. Rows are written **only by data migrations**,
from JSON files frozen beside them in `features/doctrine/migrations/data/`, one per document,
named `{slug}.json`, in the document shape below. The text was produced from the IPB PDFs outside
the repository and reviewed by a person before commit. The repository holds no PDFs, no ingestion
code and no review report. `edition` and `year` are empty on all three documents: they will only
be taken from the IPB site, which offered no page for the symbols of faith on 2026-10-27.

### Catechism file

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
        {"printed": "Rm 11.36", "reference": {"book": "Rm", "chapter": 11, "verses": [{"start": 36, "end": 36}]}},
        {"printed": "Sl 86-8", "reference": null}
      ]
    }
  ]
}
```

### Confession file

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
        {"number": 1, "text": "..."},
        {
          "number": 2,
          "text": "... são os seguintes:",
          "lists": [
            {"heading": "O Velho Testamento", "items": ["Gênesis", "..."]},
            {"heading": "O Novo Testamento", "items": ["Mateus", "..."]}
          ],
          "text_after": "Todos os quais foram dados por inspiração de Deus..."
        }
      ]
    }
  ]
}
```

| Field | Type | Description |
|-------|------|-------------|
| `slug` | `str` | Stable identifier; lowercase words joined by hyphens; equals the file name |
| `title` | `str` | pt-BR, as published |
| `kind` | `"catechism" \| "confession"` | Decides whether the document has `questions` or `chapters` |
| `position` | `int` | Order in the document list; unique across files |
| `questions[]` | `number`, `question`, `answer`, `proof_texts[]` | Catechisms only; numbered 1..N |
| `proof_texts[]` | `printed`, `reference` | One per passage, in printed order: a `;`-separated segment citing several chapters or books is split into one entry per passage |
| `reference` | `book`, `chapter`, `verses[]` or `null` | `book` is a Bible-domain `abbrev`; `verses: []` = whole chapter; spans are inclusive `{start, end}` |
| `chapters[]` | `number`, `title`, `paragraphs[]` | Confession only; numbered 1..N |
| `paragraphs[]` | `number`, `text`, optional `lists[]`, optional `text_after` | Numbered 1..N per chapter; only 1.2 has `lists`/`text_after` |

The three documents are `westminster-shorter-catechism` (107 questions),
`westminster-larger-catechism` (196 questions) and `westminster-confession-of-faith` (33 chapters).

### Adding or correcting a document

Write a new data migration that reads its own frozen files (in a subdirectory of
`features/doctrine/migrations/data/`) through `load_doctrine_documents()` and inserts or updates
the rows. The files of an applied migration never change. No other code change.

## Endpoints

### `GET /api/doctrine/`

Lists documents, ordered by `position`.

- **Auth:** none (`AllowAny`)
- **Response `200`:** `{"documents": [{"slug", "title", "kind", "edition", "year", "item_count"}]}`,
  where `item_count` is the number of questions, or of chapters for a confession, and `edition` /
  `year` are `null` while unknown
- **Conditional GET:** `ETag`; `304` when `If-None-Match` matches

### `GET /api/doctrine/{slug}/`

Returns a full document.

- **Auth:** none (`AllowAny`)
- **Path params:** `slug` — case-sensitive, must match exactly
- **Response `200`:** the document file shape above, plus `edition` and `year` (`null` while
  unknown) after `position`. A paragraph without a list has only `number` and `text`; an
  uninterpreted proof text has `"reference": null`
- **Conditional GET:** `ETag`; `304` when `If-None-Match` matches
- **Response `404`:** `{"error_code": "NOT_FOUND", "detail": "Doctrine document not found: '<slug>'"}`

Full contract: [`specs/019-doctrine-documents/contracts/doctrine-api.md`](../019-doctrine-documents/contracts/doctrine-api.md),
with the `edition` / `year` addition in [`specs/027-doctrine-database/contracts/doctrine-api.md`](../027-doctrine-database/contracts/doctrine-api.md).

## Business Rules

1. Doctrine data is **read-only** — no create, update or delete through the API, and the model is
   not registered in the Django admin.
2. Text is stored and served **as published**. Source defects (e.g. "DA SAGRADAS ESCRITURAS") are
   corrected only by a person, through a new data migration.
3. Every proof text keeps its `printed` text as published. A segment citing several passages
   ("Mt 3.16-17, e 28.19", "1Co 2.9-10: 2Tm 3.15-17") is split into one proof text per passage;
   each piece's `printed` is its part of the segment without the joining "e", "," or ":". A passage
   without a book takes the book of the previous one in the same question ("61.3" after
   "Is 60.21"), and one without a chapter takes the previous chapter too ("22-23" after "Ef 1.10").
4. A `reference` exists only when the passage is certain. A printing error ("Jo 16.1314",
   "Is 92.29", "1Re" for `1Rs`) gets the reference the 1647 English proof texts of the same
   question confirm; the `printed` text keeps the error. When the original doesn't settle it, the
   person reviewing the file picks the passage from the answer's wording ("Sl 86-8" is Sl 8.6-8,
   for "domínio sobre as criaturas"). A cross-reference to another question or document stays
   printed-only (`"reference": null`).
5. `reference.book` is exactly the Bible domain's `abbrev` (1 Timothy is `1Tn`, though printed
   `1Tm`), and the chapter and verses exist in **every** Bible version served.
6. The data migration validates every file before writing anything (`load_doctrine_documents()`):
   schema, contiguous numbering, non-blank texts, slug format and slug equal to the file name,
   unique `position`. A broken file stops `migrate` inside its transaction, so nothing is loaded and
   the server never starts on a partial set. Rows are validated again by the same DTOs when read.
   The server reads no doctrine file at startup.
7. Tests on the frozen migration files check what the loader doesn't: 107 / 196 / 33, the
   Confession 1.2 shape, rule 5 against the Bible data files (read by path; the doctrine feature
   never imports the Bible feature), and that the only references left `null` are the two
   cross-references of Larger Catechism Q153 and Q163.
8. Endpoints are **public** and the responses are not marked private.

## Errors

| Scenario | Error |
|----------|-------|
| Unknown slug (or wrong case) | `DoctrineDocumentNotFoundError` (→ 404) |
| Invalid file in a data migration | `DoctrineDataError` (`migrate` fails, nothing loaded) |
