# Research: Sunday School Lessons

Decisions taken while planning `specs/026-sunday-school/spec.md`. Each one: decision, rationale,
alternatives.

## R-01 Placement

**Decision**: a new feature app `features/sunday_school` (app label `sunday_school`) with
`models/`, `repositories/`, `services/`, `views/` packages, `dtos.py` (requests and responses),
`content_schema.py` (the content document, pure Pydantic) and `domain/` (pure rules: scripture
index, icons, positions). Domain exceptions in `core/domain/sunday_school_exceptions.py`,
re-exported by `core/domain/exceptions.py`, like `bible_exceptions`.

**Rationale**: the domain has its own models and endpoints and is used by no other feature.

**Alternatives**: inside `features/doctrine` — rejected, doctrine is read-only and file-based and
moves to the database through its own spec.

## R-02 Bible boundary

**Decision**: `sunday_school` never imports `features.bible`. It owns a pure `ScriptureIndex`
(`domain/scripture_index.py`) built from two plain mappings: verse counts per chapter per book
(`dict[str, list[int]]`, canonical order, minimum across every served translation) and book names
(`dict[str, str]`). `BibleRepositoryImpl` gains `verse_counts_by_book()` and `book_names()`
returning those primitives; `config/di.py`, the composition root, builds the index from them as a
Singleton. The migration does not need the index (R-08).

**Rationale**: the constitution forbids feature-to-feature imports; the gallery's `MemberDirectory`
is the precedent of wiring one feature's repository into another's service through DI. Plain
mappings keep the port free of Bible types. Minimum across translations implements spec FR-014
("exists in every served translation") with one lookup — the same rule as doctrine rule 5.

**Alternatives**: reading the Bible JSON by path at runtime like doctrine's test index — rejected,
it would load the 4 MB files a second time per process; importing `BibleCanon` — forbidden.

## R-03 `book_facts` derived numbers

**Decision**: the server computes them. Every lesson response (public detail and panel) carries a
top-level `books` map, one entry per book named by a `book_facts` block:
`{"Mc": {"name": "Marcos", "position": 41, "chapters": 16, "verses": 678}}`. The content itself is
returned exactly as stored.

**Rationale**: the app gets correct numbers without loading the Bible; keeping the numbers out of
`content` lets the panel editor send the content back unchanged (strict schema would refuse
extra fields inside blocks). `verses` uses the minimum across translations (differs only in Ap 12).

**Alternatives**: the app computes from its Bible snapshot — more app work, and a lesson opened
offline before the Bible was downloaded would lack the numbers; adding fields inside the block —
breaks round-trip editing.

## R-04 Content schema shape

**Decision**: Pydantic models with `extra="forbid"`, a discriminated union on `type` for the ten
blocks, non-blank required texts, `Literal` styles, `LessonIcon` enum for icons. A `list` item is
always an object `{text, proof_texts}` (never a bare string). Optional fields default to `None`
and `proof_texts` to `[]`; the stored document is the validated `model_dump(mode="json")`, so
every stored block has every field (normalized). Limits: ≤ 30 sections, ≤ 60 blocks per section,
≤ 50 items per list-like block, ≤ 40 proof texts per holder, ≤ 5000 characters per text.

**Rationale**: one shape per item is simpler for the generated Kotlin client than a
string-or-object union; normalized storage gives stable ETags and a single shape on reads. Limits
bound a malicious or mistaken body; the largest source lesson stays far below them.

**Alternatives**: `str | ListItem` — rejected (union in the client); storing as sent — rejected
(two shapes for the same thing).

## R-05 Content errors

**Decision**: request DTOs type `content` as `dict[str, object]`; the service validates it with
`LessonContent.model_validate`. A Pydantic error becomes `SundaySchoolContentInvalidError` (400
`SUNDAY_SCHOOL_CONTENT_INVALID`) whose detail lists each error as `<path>: <message>` (path like
`sections.2.blocks.0.items.1.text`), up to 10, plus `errors` in the extra context. Bible reference
and `book_facts.book` checks run after the schema, against the `ScriptureIndex`, and raise the same
error naming the path and the reference (`sections.1.blocks.3.proof: Dn 13 não existe…`).

**Rationale**: the app shows errors next to the offending field (app spec) and switches on one
code; a body field error outside `content` stays `VALIDATION_ERROR` like everywhere else.

## R-06 Icons and default section icons

**Decision**: `LessonIcon` values: `heart`, `scales`, `shield`, `plant`, `hands_praying`, `crown`,
`cross`, `book_open`, `scroll`, `flame`, `bird`, `church`, `hourglass`, `sword`, `mountains`,
`lightning` — each maps to a Phosphor icon of the same name in kebab case (`HandsPraying`,
`BookOpen`, ...; all exist in Phosphor 2.x). Default icons of the six standard sections, written
into the imported lessons and used by the app's "new lesson" template:

| Section | Icon |
|---|---|
| Contexto no Drama das Escrituras | `hourglass` |
| Objetivo teológico | `crown` |
| Estrutura / Esboço | `book_open` |
| Verdades teológicas | `shield` |
| Versículos-chave | `scroll` |
| Exortação devocional | `hands_praying` |

`sunday_school/domain/icons.py` holds the enum and `STANDARD_SECTION_ICONS` (the app copies the
table). The server does not apply defaults on write: an icon-less section stays icon-less.

**Rationale**: the spec fixes the outcome (imported lessons show icons, an icon can be changed);
storing the icon is the simplest mechanism and needs nothing from the app at render time. The
mapping was not chosen in the decision conversation; this is the plan's choice and the app spec
must copy it.

## R-07 Positions

**Decision**: positions are 0..n-1 per year, kept dense. Create appends at `max + 1` (one
aggregate query). Moving to another year appends there and re-numbers the year left. Delete
re-numbers the year. Reorder takes the full ordered id list (Bible videos precedent), checks it is
exactly the year's ids, and writes with one `bulk_update`, in a transaction with
`select_for_update` on the year row. No unique constraint on `(year, position)`: Bible videos
precedent — a constraint would make the re-numbering order-dependent; ties are ordered by id.

**Alternatives**: "move to position N" action — rejected, the app does drag and drop and already
has the full list; full list is idempotent and matches Bible videos.

## R-08 Initial load migration

**Decision**: `sunday_school/migrations/0002_load_2026_lessons.py` (data migration), reason at the
top, reading `migrations/data/2026/NN-<slug>.json` (18 files, frozen) and `migrations/data/2026/
year.json` (theme, titles order is the file order). Each lesson file holds `title`, `date` (or
null) and `content`. The migration validates `content` with the current `LessonContent` (the user
asked for the same schema) and stores the normalized dump, status `published`, `teacher` "",
authors null. Reverse deletes the 2026 lessons whose titles it created and the year if it then has
no lessons. Bible references in the files are checked by a test on the committed files
(`tests/data/test_committed_lessons.py`), not in the migration: the migration has no DI, and the
test catches a bad reference before deploy.

**Rationale**: spec FR-022; runs on the deploy's `migrate`; no dependence on database ids.
Importing the schema into a migration couples it to future schema changes; accepted because the
schema only grows (new block types, new icons), and the committed-files test fails if it ever
stops accepting the frozen files.

## R-09 Routes

**Decision**: public `api/sunday-school/` and `api/sunday-school/lessons/<int:id>/`; panel under
`api/sunday-school/manage/…` (`lessons/`, `lessons/<id>/`, `lessons/order/`, `years/`,
`years/<int:year>/`). `order/` is declared before `<int:id>/`.

**Rationale**: a separate `manage/` prefix keeps public views `AllowAny` and every panel view
`IsAuthenticated` + scope without per-method switching; drafts can never leak through a public
path.

## R-10 ETag and caching

**Decision**: public views answer through `_not_modified_or_response` (not private). Panel GETs use
`private=True` (drafts are not for shared caches).

## R-11 Scope and migrations

**Decision**: `Scope.SUNDAY_SCHOOL = "sunday_school"`; generated `core/0013_alter_panelscope_options`;
hand-written data migration `core/0014_sunday_school_scope_for_leader` copying 0012 (Liderança
`owner`, reverse removes). Access matrix test gains the scope.

## R-12 Authors

**Decision**: `created_by` / `updated_by` FKs to `settings.AUTH_USER_MODEL`, `SET_NULL`,
`related_name="+"`. Set by the service from the request user id the view passes; DTOs have no such
fields, so a body carrying them is refused as an unknown field (strict).
