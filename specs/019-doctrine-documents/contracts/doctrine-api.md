# Contract: Doctrine API

Base path in production: `/ipbcb/` (nginx). Both endpoints are public (`AllowAny`), read-only
(`GET` only; other methods `405`), and support conditional requests.

## `GET api/doctrine/`

List of documents, ordered by `position`.

**200**

```json
{
  "documents": [
    {"slug": "westminster-shorter-catechism", "title": "Breve Catecismo de Westminster", "kind": "catechism", "item_count": 107},
    {"slug": "westminster-larger-catechism", "title": "Catecismo Maior de Westminster", "kind": "catechism", "item_count": 196},
    {"slug": "westminster-confession-of-faith", "title": "A Confissão de Fé de Westminster", "kind": "confession", "item_count": 33}
  ]
}
```

- `operation_id`: `doctrine_documents_list`
- Headers: `ETag: "<sha256 of body>"`. No `Cache-Control: private`.

## `GET api/doctrine/{slug}/`

Full document. Body is the document file as described in [data-model.md](../data-model.md):
`slug`, `title`, `kind`, `position`, and `questions` (catechism) or `chapters` (confession).

- `operation_id`: `doctrine_document_retrieve`
- `slug`: case-sensitive; must match exactly.

**404** — unknown slug (including wrong case):

```json
{"error_code": "NOT_FOUND", "detail": "Doctrine document not found: 'westminster-catechism'"}
```

## Conditional requests (both endpoints)

| Request | Response |
|---------|----------|
| no `If-None-Match` | `200` + body + `ETag` |
| `If-None-Match` equal to the current tag | `304`, no body, same `ETag` |
| `If-None-Match` stale, malformed or `*` | `200` + body + current `ETag` |

The tag is derived from the response body, so any data-file change deployed to the server changes
it (FR-020).

## Field semantics the app relies on

- `proof_texts[].printed` — always present, exactly as printed; show it.
- `proof_texts[].reference` — `null` when not interpreted; the app must not try to parse
  `printed` itself. When present:
  - `book` is a Bible-domain `abbrev` (`GET api/bible/{version}/` → `[].abbrev`), e.g. `1Tn`.
  - `verses: []` → open the whole chapter; otherwise each span is inclusive.
  - The chapter and every verse exist in every Bible version the server serves.
