# Bible Domain

Read-only domain that serves Bible text data. No authentication required — fully public.

## Overview

Provides Bible versions (e.g., ARA, NAA) as structured JSON loaded from static files at startup. The Android app uses this to display Bible text offline-capable after first fetch.

## Data Model

No database models. Data lives in static JSON files under `features/bible/data/`.

### Bible JSON Structure

Each file is named `{VERSION}.json` (e.g., `ARA.json`) and contains a list of books:

```json
[
  {
    "abbrev": "Gn",
    "name": "Gênesis",
    "chapters": [
      ["Verso 1", "Verso 2", "..."],
      ["Verso 1 do cap 2", "..."]
    ],
    "headings": [
      [{"verse": 1, "level": 1, "title": "A criação do Universo"}],
      [
        {"verse": 4, "level": 1, "title": "A formação do homem"},
        {"verse": 18, "level": 1, "title": "A formação da mulher"}
      ]
    ]
  }
]
```

| Field      | Type              | Description                                      |
|------------|-------------------|--------------------------------------------------|
| `abbrev`   | `str`             | Standard abbreviation of the book                |
| `name`     | `str`             | Full name of the book (pt-BR)                    |
| `chapters` | `list[list[Verse]]` | List of chapters, each chapter is a list of verses. `Verse = str \| list[str]` — most verses are plain strings, but some entries (e.g., NAA) contain nested lists for multi-paragraph verses. |
| `headings` | `list[list[Heading]]` | Section headings (pericope titles) of the translation, one list per chapter, parallel to `chapters`. Optional in the file — a version without headings loads with `[]`. |

#### Heading

| Field   | Type  | Description                                                        |
|---------|-------|--------------------------------------------------------------------|
| `verse` | `int` | 1-based verse number the heading is shown **before**               |
| `level` | `int` | Nesting level, `1` (major section) to `3` (sub-subsection). E.g., Mt 5 in ARA: "O sermão do monte" (1) > "Jesus completa o que foi dito aos antigos" (2) > "Do homicídio" (3) |
| `title` | `str` | Heading text exactly as published in the translation               |

Within a chapter, headings are ordered by `verse`, then by `level` — several headings may precede the same verse (e.g., Mt 5:1 has a level 1 and a level 2 heading).

Headings belong to the translation: ARA and NAA have different titles for the same passage. ARA and NAA headings were taken from bibliaonline.com.br.

### Adding a new version

Drop a new `{VERSION}.json` file in `features/bible/data/`. It is loaded automatically at startup.

## Endpoints

### `GET /api/bible/`

Lists available Bible versions.

- **Auth:** none (`AllowAny`)
- **Response `200`:**

```json
{
  "versions": ["ARA", "NAA"]
}
```

Versions are returned sorted alphabetically.

### `GET /api/bible/{name}/`

Returns full Bible data for a specific version.

- **Auth:** none (`AllowAny`)
- **Path params:** `name` — version identifier (case-sensitive, must match filename stem)
- **Response `200`:** the Bible JSON structure (list of books)
- **Response `404`:**

```json
{
  "detail": "Version not found."
}
```

## Business Rules

1. Bible data is **read-only** — no create, update, or delete operations.
2. All versions are loaded **once** (lazily via DI Singleton) from JSON files. No runtime reloading.
3. Version lookup is **case-sensitive** — `ARA` and `ara` are different keys.
4. Endpoints are **public** — no authentication required.
5. When `headings` is present, it must have one entry per chapter, and every heading's `verse` must exist in its chapter. A file that breaks this fails to load at startup.

## Errors

| Scenario               | Error                          |
|------------------------|--------------------------------|
| Unknown version name   | `BibleVersionNotFound` (→ 404) |
