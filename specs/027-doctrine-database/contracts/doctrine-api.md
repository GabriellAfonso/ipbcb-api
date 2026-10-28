# Contract: Doctrine API (after the move to the database)

Unchanged from [`019-doctrine-documents/contracts/doctrine-api.md`](../../019-doctrine-documents/contracts/doctrine-api.md)
except for two **additive** fields. Paths, `operation_id`s, auth (`AllowAny`), `405` on other
methods, `ETag`/`304` behaviour and the `404` body are the same.

## `GET api/doctrine/`

```json
{
  "documents": [
    {"slug": "westminster-shorter-catechism", "title": "Breve Catecismo de Westminster", "kind": "catechism", "edition": null, "year": null, "item_count": 107},
    {"slug": "westminster-larger-catechism", "title": "Catecismo Maior de Westminster", "kind": "catechism", "edition": null, "year": null, "item_count": 196},
    {"slug": "westminster-confession-of-faith", "title": "A Confissão de Fé de Westminster", "kind": "confession", "edition": null, "year": null, "item_count": 33}
  ]
}
```

## `GET api/doctrine/{slug}/`

`slug`, `title`, `kind`, `position`, **`edition`**, **`year`**, then `questions` (catechism) or
`chapters` (confession), exactly as before.

## New fields

| Field | Type | Meaning |
|---|---|---|
| `edition` | `string \| null` | Where the text comes from, e.g. "Edição IPB". `null` when unknown. |
| `year` | `integer \| null` | Year of the document, e.g. 1647. `null` when unknown. |

Both are `null` for the three documents today. The app ignores unknown fields, so no app change is
needed. Because the bodies change, every `ETag` changes once at deploy and the app re-downloads
each document one time.
