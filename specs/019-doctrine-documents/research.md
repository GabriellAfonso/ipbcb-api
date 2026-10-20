# Research: Doctrine Documents

Decisions taken while planning. No open decisions.

## Resolved with the user (2026-10-20)

- **OD-1 Source PDFs**: not applicable. PDFs are not stored anywhere; the committed JSON is the
  source of truth.
- **OD-2 Paragraph with a list**: option B — `text`, optional `lists: [{heading, items}]`, optional
  `text_after`. Confession 1.2 is a sentence, the Old and New Testament book lists, and a sentence;
  B stores that faithfully while every other paragraph stays `{number, text}`. Blocks (A) would
  turn all ~300 paragraphs into block lists for one case; a flat list (C) mixes the "Antigo
  Testamento"/"Novo Testamento" headings with book names.
- **OD-3 Ingestion form**: not applicable. Conversion PDF → JSON happens once, outside the
  repository, reviewed by a person. No command, script or PDF dependency (dev or prod).

## Decisions

### R-01: New feature `features/doctrine`, same shape as `features/bible`

- **Decision**: a new Django app with `data/`, `dtos.py`, `loading.py`, `repositories.py`,
  `services.py`, `views/`, `urls.py`, registered in `INSTALLED_APPS`, `config/urls.py` and
  `config/di.py`. Routes `api/doctrine/` and `api/doctrine/<slug>/`.
- **Rationale**: spec says "same pattern as the Bible domain". A separate feature keeps the
  constitution rule "features never import each other" simple.
- **Alternatives**: putting it inside `features/bible` — rejected, different data and lifecycle.

### R-02: Startup validation lives in `DoctrineConfig.ready()`

- **Decision**: `ready()` loads and validates every file in `data/` (FR-012) and raises
  `ImproperlyConfigured` naming the file, the field path, the offending value and the expected
  shape. The DI Singleton repository loads the same files again on first use.
- **Rationale**: in production `migrate` runs before `gunicorn` (`compose.prod.yml`), and both
  import the app registry, so a bad file stops the container before it serves anything. A DI
  Singleton alone is lazy (the Bible one is), so a bad file would only fail on the first request.
  Loading twice costs a few tens of ms at boot for three small files; reaching into the
  `AccountsConfig` container instance to warm the Singleton would couple two apps for no gain.
- **Alternatives**: Django system check — only runs on `manage.py` commands, not on gunicorn
  workers, and is skipped by pytest-django. Rejected as the only guard.
- **Side effect**: a broken data file also breaks `manage.py` and the test run. Intended.

### R-03: What startup checks vs. what tests check

- **Decision**:
  - **Startup (generic, FR-012)**: Pydantic schema (`extra="forbid"`), numbering 1..N with no gaps
    or repeats, non-blank texts, `slug` equal to the file stem, unique `position`, `VerseSpan`
    `1 <= start <= end`.
  - **Tests on the committed files (FR-013)**: counts 107 / 196 / 33 per slug; every structured
    `book` is a Bible-domain abbreviation; every structured chapter/verse exists in every Bible
    version.
- **Rationale**: FR-014 — a new document must need only a new file, so per-document counts can't
  be a startup rule. Checking references against the Bible at startup would make the doctrine
  feature depend on the Bible feature's data at runtime; a test can read both data folders by path
  without any import between features, and runs before every commit.

### R-04: Verse existence in the data test

- **Decision**: the test builds a `(book, chapter) -> verse count` index from
  `features/bible/data/*.json`, taking the **minimum** across versions (clarification Q3), and
  checks every structured reference against it (whole-chapter references only need the chapter).
  The failure message lists every offending proof text with document, item and printed text, so
  one run shows all problems.
- **Rationale**: reading files by path keeps `features/doctrine` from importing `features/bible`;
  the Bible file format is documented in `specs/bible/spec.md`. Taking the minimum assumes extra
  verses sit at the end of a chapter, which is how ARA and NAA differ.

### R-05: Proof-text unit

- **Decision**: one proof text per `;`-separated segment as printed, in printed order in the
  question's flat list. The book-inheritance and "never guess" rules (FR-007 … FR-010) are rules
  for the person producing the JSON; the system enforces only what is mechanically checkable
  (R-03).
- **Rationale**: each segment is independently tappable in the app. Checking that `reference`
  matches the meaning of `printed` would need a reference parser in the repository, which is what
  removing ingestion avoided; human review covers it.

### R-06: Conditional GET reuses `core.http.utils._not_modified_or_response`

- **Decision**: both views call the existing helper; responses are public (no `private=True`).
- **Rationale**: same ETag scheme as every other cached read, and it already guarantees FR-018
  (tag derived from the body). The helper hashes the body per request; for a ~300 KB document that
  is a few ms, accepted for consistency.

### R-07: OpenAPI

- **Decision**: explicit `operation_id`s (`doctrine_documents_list`, `doctrine_document_retrieve`)
  as the Bible views do, plus response serializers mirroring the DTOs so the generated Android
  client gets typed models.
- **Rationale**: the Bible comment explains why operation ids must be explicit; typed responses
  matter more here because the shape is nested and discriminated by `kind`.
