# Feature Specification: Doctrine Documents in the Database

**Feature Branch**: `027-doctrine-database`

**Created**: 2026-10-27

**Status**: Draft

**Input**: User description: "Move the doctrine documents (Westminster Shorter Catechism, Larger
Catechism, Confession of Faith) from static JSON files in the repository into the database. The
public API and its responses stay the same; the documents stay read-only." (full input:
`../TODO/specify_doctrine_database_backend.md`; decision conversation: session
`2041feef-c82e-463c-b6c8-917c81b7498b`, 2026-10-27)

## Context

Today the three Westminster Standards live as JSON files committed under the doctrine feature,
validated and loaded into memory when the server starts (`specs/doctrine/spec.md`, feature
`019-doctrine-documents`). The user accepted that design temporarily but considers it too coupled
("muito acoplado"): study content is tied to the code and read from disk at startup. Study content
(Sunday school lessons, feature `026`) already lives in the database; doctrine moves there too.

Nothing changes for the person reading in the app: same endpoints, same responses, same offline
snapshot behaviour. The documents remain read-only; a correction ships as a new data migration.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Read the doctrine documents exactly as before (Priority: P1)

A church member opens Estudos → Doutrina in the Android app, sees the three documents in the same
order and opens any of them; questions, chapters, paragraphs and proof texts are identical to what
the app showed before the move.

**Why this priority**: the move is only acceptable if the reader notices nothing. Any change in
content or shape breaks the app's offline snapshot and the Bible links.

**Independent Test**: on a freshly migrated database, request the list and each document and
compare them with the responses served from the files before the move.

**Acceptance Scenarios**:

1. **Given** a freshly migrated database, **When** the app requests the document list, **Then** it receives the Shorter Catechism (107 items), the Larger Catechism (196 items) and the Confession of Faith (33 items), in that order, with the same `slug`, `title`, `kind` and `item_count` as before.
2. **Given** a freshly migrated database, **When** the app requests any of the three documents, **Then** the questions or chapters are identical to the previously committed files, a paragraph without a list still omits `lists` and `text_after`, and an uninterpreted proof text still carries an explicit `"reference": null`.
3. **Given** a document the app already has, **When** it revalidates with the `ETag` it holds, **Then** it receives `304` while the content is unchanged.
4. **Given** an unknown slug or a slug in the wrong case, **When** it is requested, **Then** the response is `404` with the same error body as today.
5. **Given** no authentication, **When** any doctrine endpoint is called, **Then** it answers normally (public).

---

### User Story 2 - Load the documents on deploy (Priority: P1)

The maintainer deploys the new version; the deploy's normal migration step creates the doctrine
table and fills it with the three documents. No manual file upload, SQL script or command on the
server is needed.

**Why this priority**: without the load the endpoints would serve an empty list in production.

**Independent Test**: run all migrations on an empty database and check the three rows; reverse
the load migration and check the rows are gone; run it forward again and check they are back.

**Acceptance Scenarios**:

1. **Given** an empty database, **When** migrations run, **Then** the three documents exist with their slugs, titles, kinds, list positions and content, and `edition` / `year` empty.
2. **Given** a document file that breaks a doctrine rule (schema, contiguous numbering, blank text, duplicate position), **When** the load runs, **Then** it fails with a message naming the document, the field and the offending value, and nothing is loaded.
3. **Given** the load already applied, **When** it is reversed, **Then** exactly the three documents it created are removed.

---

### User Story 3 - Documents cannot be edited (Priority: P2)

Nobody can change doctrine through the app, the API or the Django admin. A correction is made by a
developer as a new data migration, reviewed and deployed.

**Why this priority**: the text is the church's doctrinal standard as published; the user decided
"a doutrina não pode ser editada".

**Independent Test**: check that no endpoint accepts a write on doctrine and that the Django admin
offers no add, change or delete for doctrine documents.

**Acceptance Scenarios**:

1. **Given** any user, authenticated or not, **When** a `POST`, `PUT`, `PATCH` or `DELETE` is sent to a doctrine endpoint, **Then** it is rejected as not allowed.
2. **Given** a superuser in the Django admin, **When** they look for doctrine documents, **Then** there is no way to add, change or delete one.

---

### User Story 4 - Optional edition and year in the responses (Priority: P3)

Each document can record where its text comes from (`edition`, e.g. "Edição IPB") and the year of
the document (`year`, e.g. 1647). When present they are served in the list and in the document
response; the app may show them later.

**Why this priority**: suggested by Claude and accepted by the user, but the values are not known
yet, so they are imported empty and nothing depends on them.

**Independent Test**: check that both fields appear in the list and detail responses as `null`
for the imported documents, and that the app's existing fields are unchanged.

**Acceptance Scenarios**:

1. **Given** the imported documents, **When** the list or a document is requested, **Then** `edition` and `year` are present and `null`.
2. **Given** a document whose `edition` and `year` are set by a later data migration, **When** it is requested, **Then** both values are served.

### Edge Cases

- **Empty table** (e.g. the load reversed): the list returns `{"documents": []}` and any slug returns `404`; the server still starts.
- **The two known cross-references** (Larger Catechism Q153 and Q163) keep `"reference": null` after the move.
- **Server start**: no longer reads doctrine files and never fails because of doctrine data; a broken document can only come from a migration, which fails before the server starts.
- **ETag stability**: the `ETag` of each response depends only on the response body, so it is the same on every server and after a restart. Adding `edition` and `year` changes the bodies once, so the app downloads each document one more time after the deploy.
- **A future correction**: a new data migration changes the stored content; `updated_at` changes, the `ETag` changes and the app downloads the new version on its next revalidation.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Doctrine documents MUST be stored in the database, one record per document, with `slug` (unique), `title`, `kind` (`catechism` or `confession`), `position` (unique list order), optional `edition`, optional `year`, the document's questions or chapters as one structured value, and automatic creation and update timestamps.
- **FR-002**: The questions or chapters MUST be stored exactly as the previously committed files hold them, in the shape `specs/doctrine/spec.md` describes; the proof-text format does not change.
- **FR-003**: The records MUST NOT carry a status (draft/published) nor an author (`created_by` / `updated_by`): nobody edits doctrine.
- **FR-004**: `GET /api/doctrine/` MUST return the same body as today (`documents[]` of `slug`, `title`, `kind`, `item_count`, ordered by `position`), with `edition` and `year` added to each entry.
- **FR-005**: `GET /api/doctrine/{slug}/` MUST return the same body as today, with `edition` and `year` added, keeping the omission of `lists` / `text_after` on paragraphs without a list and the explicit `null` on uninterpreted references.
- **FR-006**: Both endpoints MUST stay public, answer `304` when `If-None-Match` matches the current `ETag`, and return `404` with the existing error body for an unknown or wrong-case slug.
- **FR-007**: Doctrine MUST be read-only: no create, update or delete endpoint, and no add, change or delete in the Django admin.
- **FR-008**: The three documents MUST be loaded by a data migration that runs in the deploy's normal migration step, from frozen copies of the current files kept beside the migration. The frozen files never change after the migration is applied; any later correction or new document is a new data migration.
- **FR-009**: The load MUST validate every document with the existing doctrine rules (schema, contiguous numbering, non-blank text, unique `position`, slug format) and fail, loading nothing, with a message naming the document, the field and the offending value.
- **FR-010**: The load MUST be reversible: the reverse removes the documents it created.
- **FR-011**: The load MUST document its reason at the top of the migration (project rule for data migrations).
- **FR-012**: The load MUST leave `edition` and `year` empty: the user wants them taken only from the IPB site, which on 2026-10-27 offered no page or download for the symbols of faith.
- **FR-013**: After the move the server MUST NOT read doctrine files at startup; the old data directory, the startup validation and the file-based reading are removed.
- **FR-014**: Tests MUST keep checking the frozen migration data: 107 / 196 / 33 items, the Confession 1.2 shape, no proof texts in the Confession, every structured reference existing in every Bible version served, and only the two known cross-references (Larger Catechism Q153 and Q163) left without a reference.
- **FR-015**: The doctrine feature MUST keep not importing the Bible feature; the reference check reads the Bible data files by path, as today.

### Key Entities

- **Doctrine document**: one of the Westminster Standards. Identified by a stable `slug` the app uses; has a published `title`, a `kind` deciding whether it holds questions (catechism) or chapters (confession), a `position` in the list, an optional `edition` (source of the text) and `year` (year of the document), its full content, and creation/update timestamps. Never edited after load except by a new data migration.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For all three documents, the content served after the move is identical, item for item, to the content served before it (only `edition` and `year` are added).
- **SC-002**: After a deploy, the doctrine section works in the app with no manual step on the server beyond the normal deploy.
- **SC-003**: 0 ways to change a doctrine document through the app, the API or the admin.
- **SC-004**: Server startup no longer depends on doctrine files: a server with the doctrine table empty starts and serves an empty list.
- **SC-005**: Opening a document in the app is no slower than before from the reader's point of view.

## Assumptions

- The app ignores unknown fields, so adding `edition` and `year` needs no app change (stated in the decision conversation; no app spec for this feature).
- The data migration validates with the doctrine DTOs of the code at the time it runs, the same approach as the Sunday school load (`026`, research R-08).
- Compact JSON for the frozen files is acceptable (~300 KB instead of ~830 KB indented).
- Whether the list reads the large content of each document or not is a plan decision.

## Out of Scope

- Editing doctrine through the API, the panel or the Django admin.
- Any change to the Android app.
- New documents (each would come as a new data migration).
- Changing the proof-text format.
- Filling `edition` and `year`.
