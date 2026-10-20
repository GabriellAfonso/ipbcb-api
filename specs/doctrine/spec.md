# Doctrine Domain

Read-only domain that serves the Westminster Standards (Shorter Catechism, Larger Catechism,
Confession of Faith) as structured data. No authentication required — fully public.

Feature history: [`specs/019-doctrine-documents`](../019-doctrine-documents/spec.md).

## Overview

The Android app shows these documents in Estudos → Doutrina and keeps an offline snapshot,
revalidated with `ETag`. Data is served, not a PDF, so the app decides the presentation and can
make Bible references tappable (opening the Bible tab).

## Data Model

No database models. Data lives in static JSON files under `features/doctrine/data/`, one per
document, named `{slug}.json`. **The committed file is the source of truth**: it is produced from
the IPB PDFs outside the repository, reviewed by a person before commit, and corrected later by
editing it directly. The repository holds no PDFs, no ingestion code and no review report.

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
| `proof_texts[]` | `printed`, `reference` | One per `;`-separated segment, in printed order |
| `reference` | `book`, `chapter`, `verses[]` or `null` | `book` is a Bible-domain `abbrev`; `verses: []` = whole chapter; spans are inclusive `{start, end}` |
| `chapters[]` | `number`, `title`, `paragraphs[]` | Confession only; numbered 1..N |
| `paragraphs[]` | `number`, `text`, optional `lists[]`, optional `text_after` | Numbered 1..N per chapter; only 1.2 has `lists`/`text_after` |

The three documents are `westminster-shorter-catechism` (107 questions),
`westminster-larger-catechism` (196 questions) and `westminster-confession-of-faith` (33 chapters).

### Adding a new document

Drop a new `{slug}.json` of an existing shape in `features/doctrine/data/` with its own `position`
and restart. No code change.

## Endpoints

### `GET /api/doctrine/`

Lists documents, ordered by `position`.

- **Auth:** none (`AllowAny`)
- **Response `200`:** `{"documents": [{"slug", "title", "kind", "item_count"}]}`, where
  `item_count` is the number of questions, or of chapters for a confession
- **Conditional GET:** `ETag`; `304` when `If-None-Match` matches

### `GET /api/doctrine/{slug}/`

Returns a full document.

- **Auth:** none (`AllowAny`)
- **Path params:** `slug` — case-sensitive, must match exactly
- **Response `200`:** the document file shape above. A paragraph without a list has only
  `number` and `text`; an uninterpreted proof text has `"reference": null`
- **Conditional GET:** `ETag`; `304` when `If-None-Match` matches
- **Response `404`:** `{"error_code": "NOT_FOUND", "detail": "Doctrine document not found: '<slug>'"}`

Full contract: [`specs/019-doctrine-documents/contracts/doctrine-api.md`](../019-doctrine-documents/contracts/doctrine-api.md).

## Business Rules

1. Doctrine data is **read-only** — no create, update or delete through the API or the admin.
2. Text is stored and served **as published**. Source defects (e.g. "DA SAGRADAS ESCRITURAS") are
   corrected only by a person editing the JSON.
3. Every proof text keeps its `printed` text. A `reference` exists only when the printed text means
   it with certainty: comparisons, malformed ranges ("Sl 86-8"), mixed separators and cross-chapter
   ranges stay printed-only. A segment without a book takes the book of the previous segment in
   the same question ("61.3" after "Is 60.21").
4. `reference.book` is exactly the Bible domain's `abbrev` (1 Timothy is `1Tn`, though printed
   `1Tm`), and the chapter and verses exist in **every** Bible version served.
5. All files are loaded **once at startup**, eagerly (`DoctrineConfig.ready()`). The server refuses
   to start if any file breaks a rule: schema, contiguous numbering, non-blank texts, slug equal to
   the file name, unique `position`. It never serves a partial set.
6. Tests on the committed files check what startup doesn't: 107 / 196 / 33, the Confession 1.2
   shape, and rule 4 against the Bible data files (read by path; the doctrine feature never imports
   the Bible feature).
7. Endpoints are **public** and the responses are not marked private.

## Errors

| Scenario | Error |
|----------|-------|
| Unknown slug (or wrong case) | `DoctrineDocumentNotFoundError` (→ 404) |
| Invalid data file at startup | `ImproperlyConfigured` (server does not start) |
