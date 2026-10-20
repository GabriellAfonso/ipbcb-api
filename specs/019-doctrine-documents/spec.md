# Feature Specification: Doctrine Documents (Westminster Standards)

**Feature Branch**: `019-doctrine-documents`

**Created**: 2026-10-20

**Status**: Draft

## Clarifications

### Session 2026-10-20

- Q: Proof texts per answer, or grouped per footnote marker inside the answer? → A: One flat list per question, in printed order, for both catechisms.
- Q: Structured book for 1 Timothy — the Bible domain's "1Tn" or the printed "1Tm"? → A: "1Tn", exactly what the Bible domain serves today; the Bible data is not changed here.
- Q: Bible version used to check that a chapter/verse exists? → A: It must exist in every version the Bible domain serves (today ARA and NAA).
- Q: Where do the source PDFs live, and is ingestion part of the feature? → A: Neither. The PDF → JSON conversion is done once, outside the repository, and reviewed by a person before commit. The committed JSON is the source of truth; later corrections are direct edits to it. No ingestion command, script, PDF dependency, stored PDFs, source URL/hash or system-generated review report.
- Q: Shape of a paragraph containing a list (Confession 1.2)? → A: `text` (sentence before), optional `lists` of `{heading, items}`, optional `text_after` (sentence after). Every other paragraph has only `text`.

**Input**: User description: "Domínio Doutrina: servir os símbolos de fé de Westminster como dado estruturado, somente leitura, para o app Android exibir em Estudos → Doutrina." (full description in the `/speckit-specify` invocation that created this file; ingestion scope later removed, see Clarifications)

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Read a catechism question by question (Priority: P1)

A church member opens Estudos → Doutrina in the Android app, picks the Westminster Shorter
Catechism and reads it as question/answer cards. Each answer shows its proof texts; tapping one
that has a structured reference opens that verse in the app's Bible tab.

**Why this priority**: the catechisms are the core teaching material of the church and the
reason the Doctrine section exists. Without the Q&A content there is nothing to show.

**Independent Test**: request the Shorter Catechism and check that it has 107 questions numbered
1–107, each with a non-empty question and answer, and that "Rm 11.36"-style proof texts come
back with both the printed text and a structured reference.

**Acceptance Scenarios**:

1. **Given** the committed data, **When** the app requests the Shorter Catechism, **Then** it receives 107 items numbered 1 to 107 in order, each with question, answer and its proof texts.
2. **Given** the committed data, **When** the app requests the Larger Catechism, **Then** it receives 196 items numbered 1 to 196 in order, with the same shape.
3. **Given** a proof text printed "Lc 24.27, 44", **When** it is served, **Then** it carries the printed text exactly as "Lc 24.27, 44" and a structured form: book `Lc`, chapter 24, verses 27 and 44.
4. **Given** the printed segments "Is 60.21" and "61.3" in one question, **When** they are served, **Then** the second carries book `Is`, chapter 61, verse 3.
5. **Given** an irregular reference such as "Hb 1:1 comparado com Lc 1.1-4" or "Sl 86-8", **When** it is served, **Then** only the printed text is present and no structured form is returned.

---

### User Story 2 - Read the Confession of Faith by chapter (Priority: P1)

A member opens the Westminster Confession of Faith and reads it chapter by chapter: each chapter
shows its number and title, followed by its numbered paragraphs. Chapter 1, paragraph 2 shows the
sentence before the list, the Old and New Testament books as two titled lists, and the sentence
after.

**Why this priority**: the Confession is the third document of the set and the church's doctrinal
standard; the section is incomplete without it.

**Independent Test**: request the Confession and check 33 chapters numbered 1–33, each with a
title and paragraphs numbered from 1 without gaps, and that chapter 1 paragraph 2 exposes its two
lists and its closing sentence separately.

**Acceptance Scenarios**:

1. **Given** the committed data, **When** the app requests the Confession, **Then** it receives 33 chapters numbered 1 to 33, each with a non-empty title and paragraphs numbered 1..N.
2. **Given** chapter 1 paragraph 2, **When** it is served, **Then** it has `text` (sentence before), two lists headed Old Testament and New Testament with one book per item, and `text_after` (sentence after).
3. **Given** any other paragraph, **When** it is served, **Then** it has only number and text.
4. **Given** the Confession, **When** it is served, **Then** no paragraph carries proof texts.

---

### User Story 3 - Browse the available documents (Priority: P2)

The app shows the Doctrine screen as a list of documents: title, whether it is a catechism or a
confession, and how many items it has, always in the order Shorter Catechism, Larger Catechism,
Confession.

**Why this priority**: needed for navigation, but the app could hard-code the three entries for a
first version; the content (Stories 1–2) delivers the value.

**Independent Test**: request the document list and check three entries in the fixed order with
counts 107, 196 and 33.

**Acceptance Scenarios**:

1. **Given** the three committed documents, **When** the app requests the list, **Then** it receives, in order: Shorter Catechism (catechism, 107), Larger Catechism (catechism, 196), Confession of Faith (confession, 33).
2. **Given** an identifier that matches no document, **When** the app requests it, **Then** it receives a `404` in the project's canonical error format.

---

### User Story 4 - Receive text corrections without an app update (Priority: P2)

The app keeps an offline snapshot of each document and revalidates it. When a maintainer fixes a
typo directly in the JSON and deploys, the next revalidation downloads the corrected document;
when nothing changed, the app gets "not modified" and keeps its snapshot.

**Why this priority**: the text is meant to be read offline, and corrections must reach phones
without publishing a new app version.

**Independent Test**: fetch a document, repeat with its validator tag and get "not modified";
change one character in the data, restart, repeat and get the full new document.

**Acceptance Scenarios**:

1. **Given** the app holds the current tag of a document, **When** it revalidates, **Then** it receives `304 Not Modified` with no body.
2. **Given** the document text was corrected and deployed, **When** the app revalidates with the old tag, **Then** it receives `200` with the corrected document and a new tag.
3. **Given** the document list, **When** the app revalidates it with its current tag, **Then** the same conditional behaviour applies.

---

### User Story 5 - Invalid data never reaches the app (Priority: P2)

A maintainer edits a JSON file by hand to fix a typo and accidentally breaks it (a question
renumbered, an answer emptied, a reference to a verse that doesn't exist). The test suite fails
before commit; and if the broken file is deployed anyway, the server refuses to start instead of
serving a partial set.

**Why this priority**: with no ingestion step, the JSON is edited by hand; the checks are the only
safety net between a typo and the members' phones.

**Independent Test**: break each rule in a copy of a data file and check that the startup
validation rejects it naming the file and the offending value; run the data tests against the
committed files and check they pass.

**Acceptance Scenarios**:

1. **Given** a data file whose question 5 is numbered 6, **When** the server starts, **Then** it refuses to start and the error names the file, the field, the value 6 and the expected 5.
2. **Given** a data file with an empty answer, title or paragraph, or whose internal identifier differs from its file name, **When** the server starts, **Then** it refuses to start.
3. **Given** the committed files, **When** the tests run, **Then** they confirm 107 / 196 / 33 items with contiguous numbering, and that every structured reference points to a chapter and verses that exist in every served Bible version.

---

### Edge Cases

- Reference segment with no book ("61.3" after "Is 60.21") → structured with the book of the previous segment in the same question's proof-text list.
- Verse list within one chapter ("Lc 24.27, 44") → one structured reference with two verse entries.
- Verse range ("Lc 1.1-4") → one structured range entry, start 1, end 4.
- Whole-chapter reference ("Sl 23") → structured with book and chapter and no verses, meaning the whole chapter.
- Cross-chapter or otherwise irregular reference ("Gn 1.1–2.3", "Hb 1:1 comparado com Lc 1.1-4", "Sl 86-8") → printed text only.
- Book printed differently from the Bible domain's abbreviation ("1Tm" vs "1Tn") → structured with the Bible-domain abbreviation, printed text unchanged.
- Verse that exists in ARA but not in NAA (or vice versa) → printed text only.
- Source defect such as "DA SAGRADAS ESCRITURAS" in the Confession chapter 1 title → kept as published unless a person decides to correct it in the JSON.
- Unknown document identifier, or wrong case → `404` canonical error.
- Extra data file dropped into the data folder for a new document of a supported shape → served after restart with no code change (FR-014).
- Revalidation with a malformed or stale tag → full `200` response.

## Requirements *(mandatory)*

### Functional Requirements

**Documents and content**

- **FR-001**: The system MUST serve three documents: Westminster Shorter Catechism (107 Q&A), Westminster Larger Catechism (196 Q&A) and Westminster Confession of Faith (33 chapters).
- **FR-002**: Catechism items MUST have a number, the question text, the answer text and zero or more proof texts, as one flat list per question in printed order. Proof texts are not tied to a part of the answer.
- **FR-003**: Confession chapters MUST have a number, a title and paragraphs numbered from 1; paragraphs MUST NOT have proof texts.
- **FR-004**: A paragraph MUST have `text`. It MAY also have an ordered list of titled lists (`heading` and `items`) and a `text_after` shown after the lists. Confession chapter 1 paragraph 2 MUST use this shape for the canonical books (sentence before, Old Testament list, New Testament list, sentence after); every other paragraph has only `text`.
- **FR-005**: All text MUST be stored and served as published; source defects are corrected only by a person editing the JSON.

**Bible references** (rules the committed data follows)

- **FR-006**: Every proof text MUST carry its printed text exactly as published (e.g., "Rm 11.36", "Lc 24.27, 44").
- **FR-007**: A proof text MAY carry a structured form — book, chapter, and a list of verses and/or verse ranges (an empty list means the whole chapter) — only when the printed text has that meaning with certainty. The book MUST be exactly the abbreviation the Bible domain serves, even where it differs from the printed one (1 Timothy is printed "1Tm" but structured as "1Tn").
- **FR-008**: A segment without a book is structured with the book of the previous segment in the same question's proof-text list (e.g., "61.3" printed after "Is 60.21").
- **FR-009**: An irregular reference (comparisons, malformed ranges such as "Sl 86-8", mixed separators, cross-chapter ranges) MUST carry only the printed text. Nothing is guessed.
- **FR-010**: A structured reference MUST point to a book, chapter and verses that exist in every Bible version the Bible domain serves (today ARA and NAA); otherwise the proof text carries only the printed text.

**Data files and validation**

- **FR-011**: Each document MUST live in one static JSON file in the repository, loaded once at server startup. No database. The committed file is the source of truth; producing it from the IPB PDFs happens outside the repository and is reviewed by a person before commit. A text correction is an edit to that file plus a deploy.
- **FR-012**: The server MUST refuse to start if any data file is invalid: schema mismatch, non-contiguous numbering (questions, chapters, paragraphs), empty question/answer/title/paragraph/list item, identifier different from the file name, or two documents with the same list position. The error MUST name the file, the field, the offending value and the expected shape. It MUST NOT serve a partial set.
- **FR-013**: The test suite MUST check the committed files for: 107 / 196 / 33 items, contiguous numbering, every structured book being a Bible-domain abbreviation, and every structured chapter/verse existing in every served Bible version (FR-010).
- **FR-014**: Adding a new document of an existing shape (question/answer or chapter/paragraph) MUST require only a new data file — no code change. Its position in the list MUST be defined in the data.

**API**

- **FR-015**: All endpoints MUST be public (no authentication) and read-only.
- **FR-016**: The system MUST list documents with identifier, title, type (`catechism` or `confession`) and item count (questions for catechisms, chapters for the Confession), in the fixed order Shorter, Larger, Confession.
- **FR-017**: The system MUST return a full document by identifier; an unknown identifier MUST answer `404` in the canonical error format.
- **FR-018**: Both the list and the document MUST support conditional requests: a validator tag derived from the content, and `304 Not Modified` when the client's tag matches. Any change to the served content MUST produce a different tag.

### Key Entities

- **Doctrine document**: identifier (stable, matches its file name), title, type (catechism / confession), list position, and its items. Catechisms hold questions; confessions hold chapters.
- **Catechism question**: number, question, answer, proof texts.
- **Confession chapter**: number, title, paragraphs.
- **Paragraph**: number, text, optional titled lists, optional text after the lists.
- **Proof text (Bible reference)**: printed text (always), optional structured form.
- **Structured reference**: Bible-domain book abbreviation, chapter, verses and verse ranges.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of the 107 + 196 questions and 33 chapters are available in the app, with no numbering gaps.
- **SC-002**: 100% of proof texts show their printed text exactly as published; 0 structured references point to a verse that doesn't exist in any served Bible version.
- **SC-003**: A text correction deployed to the server reaches a phone holding an offline snapshot on its next revalidation, with no app release.
- **SC-004**: An unchanged document revalidation transfers no document body.
- **SC-005**: A broken data file never results in the app receiving a partial document set: the tests fail, and the server does not start.
- **SC-006**: A fourth document of an existing shape is published by adding one data file and redeploying, with zero code changes.

## Assumptions

- The IPB text is public and may live in the repository as JSON.
- Identifiers are stable English slugs (`westminster-shorter-catechism`, `westminster-larger-catechism`, `westminster-confession-of-faith`); titles are pt-BR as published.
- The Confession's item count is its number of chapters, not paragraphs.
- Documents are a few hundred KB at most, so serving each document whole (no pagination) fits the offline-snapshot use; this matches the Bible domain.
- The canonical error format is the one defined in `specs/001-api-error-handling`.
- The three JSON files are produced outside the repository and reviewed by a person; their correctness against the PDFs is that person's responsibility. The system checks structure and Bible references, not wording.

## Out of Scope

- Storing the source PDFs, their URLs or hashes.
- Any ingestion command or script, any PDF-reading dependency, and any system-generated review report.
- Editing by church leadership (in the app or in the admin).
- Server-side search; reverse lookup by Bible reference.
- Other documents (Creeds, Canons of Dort, Belgic Confession) — the model supports them, but they are not added here.
- The Android app side (separate spec).
