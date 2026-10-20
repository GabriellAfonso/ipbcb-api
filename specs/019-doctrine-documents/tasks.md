---

description: "Task list for feature 019 — doctrine documents (Westminster Standards)"
---

# Tasks: Doctrine Documents (Westminster Standards)

**Input**: Design documents from `specs/019-doctrine-documents/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/doctrine-api.md, quickstart.md

**Tests**: required by CLAUDE.md §10 and by spec FR-013 (tests on the committed files), so they are
included. Unit tests use fixture files in a temp dir; data tests read the real committed files.

**Organization**: grouped by user story. US1 = catechisms (P1), US2 = Confession (P1), US3 = document
list (P2), US4 = conditional GET (P2), US5 = invalid data never reaches the app (P2).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1 … US5 (spec.md user stories)
- Paths are relative to the repository root. Tests and commands run from `server/`, with
  `.venv_windows` active, in PowerShell.

## Constraints that apply to every task

- **mypy strict runs over the whole `server/` tree, tests included**, on every commit. When a method
  is added to the `DoctrineRepository` protocol, add it to `DoctrineRepositoryImpl` and to
  `FakeDoctrineRepository` in the same task.
- **`DoctrineConfig.ready()` validates `features/doctrine/data/` on every import of the app**,
  including the test run. Never commit a file in `data/` that fails validation. An empty `data/`
  is valid (zero documents).
- **The three real JSON files are produced outside the repository and reviewed by a person**
  (spec FR-011). No task generates them, and no task edits their wording. A data-test failure is
  reported to the user; it is never fixed by loosening a test.
- Functions 4–20 lines, max 2 levels of indentation, a docstring with intent plus one example on
  public functions, exception messages that name the offending value and the expected shape
  (CLAUDE.md §8–9).
- The domain spec `specs/doctrine/spec.md` and the code go in the same commit (CLAUDE.md §6.2).
- `features/doctrine` never imports `features.bible`. Only the test-only verse index reads the Bible
  files, by path (research R-04).

---

## Phase 1: Setup

**Purpose**: baseline and an empty, registered app.

- [X] T001 Run `python -m pytest features/bible` and `python -m mypy .` from `server/` and record that both are green before any change
- [X] T002 Create the app skeleton: `server/features/doctrine/__init__.py`, `server/features/doctrine/apps.py` (`DoctrineConfig(AppConfig)` with `name = "features.doctrine"`, no `ready()` yet), `server/features/doctrine/data/.gitkeep`, `server/features/doctrine/views/__init__.py` (empty), and test packages `server/features/doctrine/tests/__init__.py`, `tests/unit/__init__.py`, `tests/integration/__init__.py`, `tests/data/__init__.py`, plus an empty `tests/fixtures/` directory
- [X] T003 Add `"features.doctrine"` to `INSTALLED_APPS` in `server/config/settings/base.py`, right after `"features.bible"`

**Checkpoint**: `python manage.py check` passes; nothing is served yet.

---

## Phase 2: Foundational (blocking prerequisites)

**Purpose**: the DTOs, the loader with the generic startup rules, the repository, service, exception
and DI wiring that every story needs.

- [X] T004 Create `server/features/doctrine/dtos.py` with the served DTOs from `specs/019-doctrine-documents/data-model.md`, all on `StrictBaseModel` (`core.application.dtos.strict_base`):
  - `VerseSpan(start: int, end: int)` with a `model_validator(mode="after")` requiring `1 <= start <= end`, message naming both values.
  - `BibleReference(book: str, chapter: int, verses: list[VerseSpan])`, `chapter >= 1` via `Field(ge=1)`; docstring: empty `verses` means the whole chapter.
  - `ProofText(printed: str, reference: BibleReference | None)`.
  - `CatechismQuestion(number: int, question: str, answer: str, proof_texts: list[ProofText])`.
  - `ParagraphList(heading: str, items: list[str] = Field(min_length=1))`.
  - `ConfessionParagraph(number: int, text: str, lists: list[ParagraphList] | None = None, text_after: str | None = None)`; `lists`, when present, `min_length=1`.
  - `ConfessionChapter(number: int, title: str, paragraphs: list[ConfessionParagraph])`.
  - `CatechismDocument(slug, title, kind: Literal["catechism"], position: int, questions)` and `ConfessionDocument(slug, title, kind: Literal["confession"], position: int, chapters)`.
  - `DoctrineDocument = Annotated[CatechismDocument | ConfessionDocument, Field(discriminator="kind")]`.
  - `DoctrineDocumentSummary(slug, title, kind: Literal["catechism", "confession"], item_count: int)`.
  - Declare one shared `_NonBlankText = Annotated[str, StringConstraints(min_length=1, strip_whitespace=False), AfterValidator(_require_non_blank)]` and use it for every text field (`printed`, `question`, `answer`, `heading`, list items, `text`, `text_after`, `title`, `book`). Text is stored **as published**, so it is never stripped.
  - Each document model gets `item_numbers(self) -> list[int]` returning the numbers of its top-level items, so the loader can check contiguity without knowing the kind.
- [X] T005 [P] Create `server/features/doctrine/tests/unit/test_doctrine_dtos.py`: valid minimal catechism and confession parse; `VerseSpan(5, 4)` and `VerseSpan(0, 1)` rejected; blank and whitespace-only text rejected for each text field; unknown key rejected (`extra_forbidden`); `kind` routes to the right model through a `TypeAdapter(DoctrineDocument)`; `lists=[]` rejected; a paragraph without `lists`/`text_after` dumps without them when dumped with `exclude_none=True`
- [X] T006 Create `server/features/doctrine/loading.py`:
  - `class DoctrineDataError(ValueError)` with a docstring saying it only happens at startup and never reaches HTTP.
  - `load_doctrine_documents(data_dir: Path) -> list[DoctrineDocument]`: reads every `*.json` in `data_dir` (sorted by name, UTF-8), validates each through `TypeAdapter(DoctrineDocument)`, applies the rules below, and returns the documents sorted by `position`.
  - Per-file rules, each a small module-level function raising `DoctrineDataError` with file name, field path, offending value and expected shape:
    - `_require_slug_matches_file(document, path)`: `slug` matches `^[a-z0-9]+(-[a-z0-9]+)*$` and equals `path.stem`.
    - `_require_contiguous(numbers, file, field)`: numbers are exactly `1..N`, N ≥ 1. Message example: `"westminster-shorter-catechism.json: questions[4].number is 6; expected 5 (numbering must be 1..N with no gaps or repeats)"`.
    - Applied to top-level items and, for a confession, to each chapter's `paragraphs`.
  - Cross-file rule `_require_unique_positions(documents)`: two documents with the same `position` → error naming both files.
  - A pydantic `ValidationError` is re-raised as `DoctrineDataError` naming the file and keeping pydantic's message (`from exc`).
  - `DOCTRINE_DATA_DIR = Path(__file__).parent / "data"`.
- [X] T007 [P] Create fixture files under `server/features/doctrine/tests/fixtures/valid/`: `tiny-catechism.json` (kind catechism, position 1, 2 questions, one with proof texts incl. a `null` reference and a whole-chapter `verses: []`) and `tiny-confession.json` (kind confession, position 2, 2 chapters, chapter 1 with paragraph 2 using `lists` (two lists) and `text_after`). Add `server/features/doctrine/tests/fixture_dirs.py` with a helper `copy_fixture_dir(name: str, tmp_path: Path) -> Path` and `write_document(tmp_path: Path, file_name: str, body: dict[str, object]) -> Path` so each test builds its own broken variant in `tmp_path` instead of committing one file per rule
- [X] T008 Create `server/features/doctrine/tests/unit/test_loading.py` (depends on T006, T007): the valid fixture dir loads and is ordered by `position`; an empty dir loads `[]`; and one test per rule, each asserting `DoctrineDataError` and that the message names the file, the field and the offending value: gap in questions, repeated number, numbering starting at 0, gap in a chapter's paragraphs, slug ≠ file stem, slug with uppercase, duplicate `position` across two files, empty answer (pydantic path), invalid JSON
- [X] T009 Add `DoctrineDocumentNotFoundError(NotFoundError)` to `server/core/domain/exceptions.py`, right after `BibleVersionNotFound`, same style: `__init__(self, slug: str)`, message `f"Doctrine document not found: '{slug}'"`, attribute `slug`
- [X] T010 Create `server/features/doctrine/repositories.py` (following `server/features/bible/repositories.py`):
  - `DoctrineRepository(Protocol)` with `list_documents(self) -> list[DoctrineDocument]` and `get_document(self, slug: str) -> DoctrineDocument | None`.
  - `DoctrineRepositoryImpl.__init__(self, data_dir: Path = DOCTRINE_DATA_DIR)` loads once with `load_doctrine_documents` and keeps the ordered list plus a `dict[str, DoctrineDocument]` by slug. Lookup is case-sensitive.
- [X] T011 Create `server/features/doctrine/tests/fakes.py` with `FakeDoctrineRepository`, an in-memory implementation of the whole protocol built from a `list[DoctrineDocument]` given to the constructor (docstring: exists because mypy checks tests against the full protocol)
- [X] T012 Create `server/features/doctrine/services.py`: `DoctrineService.__init__(self, doctrine_repository: DoctrineRepository)`; `list_documents(self) -> list[DoctrineDocumentSummary]` (item count = `len(questions)` or `len(chapters)`, via a module-level `_summarize(document)`); `get_document(self, slug: str) -> DoctrineDocument` raising `DoctrineDocumentNotFoundError(slug)` when the repository returns `None`
- [X] T013 [P] Create `server/features/doctrine/tests/unit/test_doctrine_service.py` using `FakeDoctrineRepository`: summaries keep repository order with the right `kind` and `item_count` for both kinds; `get_document` returns the document; unknown slug and wrong-case slug raise `DoctrineDocumentNotFoundError` with the slug in the message
- [X] T014 Register in `server/config/di.py`: import `DoctrineRepositoryImpl` and `DoctrineService`; add `doctrine_repository = providers.Singleton(DoctrineRepositoryImpl)` and `doctrine_service = providers.Factory(DoctrineService, doctrine_repository=doctrine_repository)` right after the bible providers; add `"features.doctrine.views"` to `wiring_config.modules` after `"features.bible.views"`

**Checkpoint**: `python -m pytest features/doctrine` and `python -m mypy .` are green.

---

## Phase 3: User Story 1 — Read a catechism question by question (Priority: P1) 🎯 MVP

**Goal**: `GET api/doctrine/{slug}/` returns a catechism with its questions and proof texts; unknown
slug → canonical `404`.

**Independent Test**: with the valid fixture dir injected, `GET api/doctrine/tiny-catechism/` returns
the questions with `printed` and `reference` as in the file; `GET api/doctrine/nope/` → `404 NOT_FOUND`.

- [X] T015 [US1] Create `server/features/doctrine/views/__init__.py` with `DoctrineDetailView(APIView)`, `permission_classes = [AllowAny]`, `@extend_schema(operation_id="doctrine_document_retrieve")`, `@inject get(self, request, slug: str, doctrine_service: DoctrineService = Provide[Container.doctrine_service])` returning `Response(document.model_dump(exclude_none=True))` for now (ETag comes in US4). Comment, like the Bible view, that `DoctrineDocumentNotFoundError` bubbles up to `custom_exception_handler`
- [X] T016 [US1] Create `server/features/doctrine/urls.py` (`app_name = "doctrine"`, `path("api/doctrine/<slug:slug>/", DoctrineDetailView.as_view(), name="doctrine-detail")`) and add `path("", include("features.doctrine.urls"))` to `server/config/urls.py` after the bible include
- [X] T017 [US1] Create `server/features/doctrine/tests/integration/conftest.py` with a fixture `fixture_doctrine(di_container, tmp_path)` that copies the valid fixture dir and does `with di_container.doctrine_repository.override(providers.Object(DoctrineRepositoryImpl(dir))): yield` (pattern from `server/conftest.py` `di_container`)
- [X] T018 [US1] Create `server/features/doctrine/tests/integration/test_doctrine_api.py`, class `TestCatechismDetail` (uses `fixture_doctrine`): `200` without auth; body equals the fixture file content (`kind`, `position`, questions in order); a `null` reference stays `null`; whole-chapter reference keeps `verses: []`; `404` with `error_code == "NOT_FOUND"` and the slug in `detail` for an unknown slug and for the slug in different case; `POST` → `405`

**Checkpoint**: catechism content is served end-to-end.

---

## Phase 4: User Story 2 — Read the Confession of Faith by chapter (Priority: P1)

**Goal**: the same endpoint serves a confession; paragraph 1.2 exposes `lists` and `text_after`; other
paragraphs carry only `number` and `text`.

**Independent Test**: `GET api/doctrine/tiny-confession/` returns chapters with paragraphs; chapter 1
paragraph 2 has two lists and `text_after`; paragraph 1 has exactly the keys `number`, `text`.

- [X] T019 [US2] In `server/features/doctrine/tests/integration/test_doctrine_api.py`, add class `TestConfessionDetail`: chapters and paragraphs in order; paragraph 1.2 has `lists` with headings and items in order and `text_after`; every other paragraph's keys are exactly `{"number", "text"}` (proves `exclude_none=True`); no paragraph has a `proof_texts` key

**Checkpoint**: both document shapes are served.

---

## Phase 5: User Story 3 — Browse the available documents (Priority: P2)

**Goal**: `GET api/doctrine/` lists `slug`, `title`, `kind`, `item_count`, ordered by `position`.

**Independent Test**: with the fixture dir, the list is `[tiny-catechism (catechism, 2), tiny-confession (confession, 2)]`.

- [X] T020 [US3] In `server/features/doctrine/views/__init__.py`, add `DoctrineListView(APIView)`, `AllowAny`, `@extend_schema(operation_id="doctrine_documents_list")`, returning `Response({"documents": [s.model_dump() for s in doctrine_service.list_documents()]})`. Add `path("api/doctrine/", DoctrineListView.as_view(), name="doctrine-list")` before the detail route in `server/features/doctrine/urls.py`
- [X] T021 [US3] In `server/features/doctrine/tests/integration/test_doctrine_api.py`, add class `TestDocumentList`: `200` without auth; exact body for the fixture dir; order follows `position` even when file names sort the other way (write a third fixture document with `position: 0` named `z-first.json`)

**Checkpoint**: navigation works.

---

## Phase 6: User Story 4 — Receive text corrections without an app update (Priority: P2)

**Goal**: both endpoints answer `304` to a matching `If-None-Match`, and any content change changes the tag.

**Independent Test**: GET, repeat with the `ETag` → `304` with no body; change one character in a
fixture answer, rebuild the repository, repeat with the old tag → `200` with a new `ETag`.

- [X] T022 [US4] In `server/features/doctrine/views/__init__.py`, return both responses through `_not_modified_or_response(request, body)` from `server/core/http/utils.py` (public: no `private=True`, research R-06)
- [X] T023 [US4] In `server/features/doctrine/tests/integration/test_doctrine_api.py`, add class `TestConditionalGet`, for both the list and a document: `ETag` present and no `Cache-Control: private`; matching tag → `304` with empty body and same `ETag`; stale, malformed and `*` tags → `200`; after changing one character of an answer in the copied fixture and re-overriding the repository with a new `DoctrineRepositoryImpl`, the old tag → `200` and a different `ETag`; the list's tag also changes when a title changes

**Checkpoint**: offline snapshot revalidation works.

---

## Phase 7: User Story 5 — Invalid data never reaches the app (Priority: P2)

**Goal**: the server refuses to start on an invalid data file; tests on the committed files guard
counts, the Confession 1.2 shape and Bible references.

**Independent Test**: point the startup check at a broken copy → `ImproperlyConfigured` naming file,
field and value; run `python -m pytest features/doctrine/tests/data` against the committed files → green.

- [X] T024 [US5] In `server/features/doctrine/apps.py`, add `DoctrineConfig.ready()` calling a module-level `validate_doctrine_data(data_dir: Path = DOCTRINE_DATA_DIR) -> None` that runs `load_doctrine_documents` and re-raises `DoctrineDataError` as `django.core.exceptions.ImproperlyConfigured` (`from exc`). Comment why it is eager (research R-02: `migrate` runs before `gunicorn` in `compose.prod.yml`, and the DI Singleton alone is lazy). Import `loading` inside `ready()` like the other app configs do
- [X] T025 [P] [US5] Create `server/features/doctrine/tests/unit/test_startup_validation.py`: `validate_doctrine_data` on the valid fixture dir returns `None`; on a broken copy (question 2 renumbered to 3) raises `ImproperlyConfigured` whose message names the file, `questions[1].number`, `3` and `2`; on an empty dir returns `None`
- [X] T026 [US5] Create `server/features/doctrine/tests/bible_verse_index.py` (test-only, research R-04): `BibleVerseIndex.from_files(paths: list[Path]) -> BibleVerseIndex` reads each Bible JSON (`[{abbrev, name, chapters: list[list[Verse]]}]`, format in `specs/bible/spec.md`) and keeps, per `(abbrev, chapter)`, the **minimum** verse count across files; a chapter missing in any file is absent. Methods `has_book(book) -> bool` and `missing_verses(reference: BibleReference) -> str | None` (returns a reason such as `"Rm 11 has 36 verses in every version; got 37"`, or `None`). Module constant `BIBLE_DATA_FILES = sorted((Path(__file__).resolve().parents[2] / "bible" / "data").glob("*.json"))` — computed **by path** (`server/features/bible/data/*.json`), never by importing `features.bible`
- [X] T027 [P] [US5] Create `server/features/doctrine/tests/unit/test_bible_verse_index.py` with two tiny Bible JSON files written to `tmp_path`: minimum across versions; chapter missing in one version is absent; whole-chapter reference only needs the chapter; verse beyond the minimum is reported with the counts; unknown book reported; a multi-paragraph verse (`list[str]`) counts as one verse
- [X] T028 [US5] Create `server/features/doctrine/tests/data/test_committed_documents.py`, reading `DOCTRINE_DATA_DIR` through `load_doctrine_documents` (spec FR-013). Every test **skips with an explicit reason while `data/` holds no `.json`** (so this task can be committed before the real files), and fails otherwise:
  - The set of slugs is exactly `westminster-shorter-catechism`, `westminster-larger-catechism`, `westminster-confession-of-faith`, in that `position` order.
  - Counts: 107 questions, 196 questions, 33 chapters.
  - Confession chapter 1 paragraph 2 has exactly two `lists` and a `text_after`; no other paragraph in any chapter has `lists` or `text_after`.
  - The Confession has no proof texts (structural: `ConfessionParagraph` has no such field — assert the raw JSON has no `proof_texts` key anywhere under `chapters`).
  - Every `reference.book` is a Bible abbreviation (`BibleVerseIndex.has_book`).
  - Every `reference` exists in every Bible version (`missing_verses` is `None`).
  - Reference tests collect **all** offenders and fail once with a list `"<slug> Q<n> '<printed>': <reason>"`, so one run shows every problem.
- [X] T029 [US5] Add the three real files `server/features/doctrine/data/westminster-shorter-catechism.json`, `westminster-larger-catechism.json` and `westminster-confession-of-faith.json`, **supplied by the user** (produced outside the repository and reviewed by a person). Run `python manage.py check` and `python -m pytest features/doctrine/tests/data`. If anything fails, stop and report every failure to the user; do not edit the files' wording or loosen a test. Remove the `.gitkeep` from `data/`

**Checkpoint**: the real data is served, the server refuses broken data, and the committed files pass
every data test.

---

## Phase 8: Polish & cross-cutting

- [X] T030 [P] Create `server/features/doctrine/serializers.py` with OpenAPI-only serializers mirroring the DTOs (`VerseSpanSerializer`, `BibleReferenceSerializer`, `ProofTextSerializer`, `CatechismQuestionSerializer`, `ParagraphListSerializer`, `ConfessionParagraphSerializer`, `ConfessionChapterSerializer`, `CatechismDocumentSerializer`, `ConfessionDocumentSerializer`, `DoctrineDocumentSummarySerializer`, `DoctrineDocumentListSerializer`), and use them in both views' `extend_schema(responses=...)`; the detail uses `PolymorphicProxySerializer(component_name="DoctrineDocument", serializers=[...], resource_type_field_name="kind")` and `404: None`. Serializers are never used to build responses (research R-07). Check `python manage.py spectacular --validate --fail-on-warn` has no new warning
- [X] T031 [P] Create the domain spec `specs/doctrine/spec.md` in the style of `specs/bible/spec.md`: overview, JSON structure (from data-model.md), endpoints (from contracts/doctrine-api.md), business rules (read-only, public, startup validation, committed JSON is the source of truth and corrections are direct edits, reference rules FR-006…FR-010), errors table
- [X] T032 [P] Create `docs/features/doctrine.md` following `docs/features/bible.md`
- [X] T033 Run `ruff check`, `ruff format` and `python -m mypy .` from `server/`, then the full suite `python -m pytest` (end of feature), then walk through `specs/019-doctrine-documents/quickstart.md`; every step must be covered by a passing test or done by hand and reported
- [X] T034 Check file sizes and function lengths: every file under `server/features/doctrine/` stays under 500 lines and every new function within 4–20 lines (`dtos.py` and `serializers.py` are declarations, functions inside them still count)

---

## Dependencies & Execution Order

- **Setup (T001–T003)** → **Foundational (T004–T014)** → stories.
- Inside Foundational: T004 → T006 → T008; T007 alongside T006; T009 → T010 → T011/T012 → T013; T014 after T010 and T012.
- **US1 (T015–T018)** depends on Foundational.
- **US2 (T019)** depends on US1's view and route (same endpoint, different shape).
- **US3 (T020–T021)** depends on Foundational and T016 (the urls module exists).
- **US4 (T022–T023)** depends on US1 and US3 (wraps both views).
- **US5**: T024–T027 depend only on Foundational; T028 on T026; **T029 needs the three JSON files from the user**.
- **Polish (T030–T034)** last. T031 lands in the same commit as the code (CLAUDE.md §6.2).

## Parallel Opportunities

- Foundational: T005 alongside T006; T007 alongside T006; T013 alongside T014.
- After Foundational: US1 (T015–T018) and the US5 startup/index work (T024–T027) are independent tracks.
- Polish: T030, T031 and T032 touch different files.

```text
# Two tracks after T014
Track A (API):   T015 detail view → T016 urls → T017 conftest → T018 → T019 → T020/T021 list → T022/T023 ETag
Track B (guard): T024 ready() → T025 | T026 verse index → T027 → T028 data tests (skipping)
Join:            T029 real data (from the user) → Polish
```

## Implementation Strategy

1. **MVP = US1 + US2 on fixtures** (T001–T019): both document shapes served, verified without the real data.
2. **US3 + US4** (T020–T023): list and conditional GET, still on fixtures.
3. **US5** (T024–T028): startup guard and data tests, committed with the data tests skipping.
4. **Real data** (T029): only when the user supplies the three reviewed JSON files.
5. **Polish** (T030–T034), then `/ship-dev`.

Commit points that keep the hook green: after T014, T018, T023, T028, T029. Never commit a `data/`
file that fails `python manage.py check`.
