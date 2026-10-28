# Feature Specification: Sunday School Lessons

**Feature Branch**: `026-sunday-school`

**Created**: 2026-10-27

**Status**: Draft

**Input**: User description: "Put the Sunday school (Escola Bíblica Dominical, EBD) lessons in the
database, served to the Android app as structured content, and editable from the app's management
panel." (full request — current state, decisions and their reasons — in
`../TODO/specify_sunday_school_backend.md`; decided in session
`2041feef-c82e-463c-b6c8-917c81b7498b`, 2026-10-27.)

## Context

Today the EBD lessons exist only as PDFs and PowerPoint decks sent around on WhatsApp; the app's
Estudos tab shows "Escola Bíblica Dominical" as "Em breve". This feature adds a new domain,
`sunday_school`, that stores each lesson as structured content (sections of typed blocks), serves
the published lessons publicly, lets leadership write and order them from the panel, and loads this
year's 18 lessons on deploy.

The name was chosen by the user: these are EBD lessons only, not generic "studies". There are no
categories and no series inside a year.

### Relation to other specs

- **`specs/doctrine/spec.md`** — closest precedent: public read, `ETag`/`304`, proof texts as
  `{printed, reference}` with the Bible's `abbrev`, references checked against every Bible version.
- **`specs/012-feature-role-permissions/`** — gains the scope `sunday_school`.
- **`specs/bible/spec.md`** — ordering precedent (full ordered id list); source of book abbrevs,
  chapter and verse counts.
- **`specs/001-api-error-handling/`** — every error follows its `{"error_code", "detail"}` format.

## Definitions

### Year

One year of lessons, with an optional theme ("2026 — O Drama das Escrituras"). The theme lives once
on the year, not on every lesson. A year row is created implicitly the first time a lesson is saved
for it; it is never created or deleted directly through the API.

### Lesson

A title, an optional date, an optional free-text teacher name, a status (`draft` or `published`), a
position inside its year and a content document.

### Published year

A year with at least one published lesson. Only published years and published lessons are visible
publicly.

### Default year

The most recent published year — not the calendar year. In January 2027, before any 2027 lesson is
published, 2026 stays the default.

### Content document

Ordered sections, each with a title, an optional icon and at least one block. A block is one of a
closed list of ten types. Text fields accept only `**bold**` and `*italic*` as markup.

### Bible reference

`{printed, reference}` exactly like doctrine proof texts: `printed` is the text as written;
`reference` is `{book, chapter, verses: [{start, end}]}` (book = Bible `abbrev`, `verses: []` = the
whole chapter) or `null` when the passage cannot be pinned.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Anyone reads this year's lessons (Priority: P1)

A member opens Estudos → Escola Bíblica Dominical without signing in. The app shows "2026 — O Drama
das Escrituras" with its 18 lessons in Bible order; tapping "Daniel" shows its sections
with icons, key verses as cards with tappable references, and the Daniel timeline.

**Why this priority**: this is what replaces the PDFs on WhatsApp; it is the whole value for the
church.

**Independent Test**: after migrating, request the index and one lesson without a token; expect the
2026 year with its theme, 18 lessons ordered by position, and a lesson body that validates against
the content schema; repeat with the returned ETag and expect 304.

**Acceptance Scenarios**:

1. **Given** published 2026 lessons and no other year, **When** anyone requests the index, **Then**
   they get years `[2026]` with theme, default year 2026 and the 2026 lessons as summaries (id,
   title, date, teacher, position) ordered by position.
2. **Given** 2026 has published lessons and 2027 only drafts, **When** the index is requested,
   **Then** 2027 is not listed and 2026 is the default.
3. **Given** a 2027 lesson is published, **When** the index is requested, **Then** years are
   `[2027, 2026]` and 2027 is the default.
4. **Given** a year is requested explicitly (`?year=2026`), **Then** the answer has the same shape
   with that year's lessons; a year that does not exist or has no published lesson is 404
   `SUNDAY_SCHOOL_YEAR_NOT_FOUND` naming the year.
5. **Given** a published lesson, **When** it is requested by id, **Then** the answer has its fields,
   its year and theme, and its full content; a draft or unknown id is 404
   `SUNDAY_SCHOOL_LESSON_NOT_FOUND`.
6. **Given** a response already fetched, **When** it is fetched again with the same ETag and nothing
   changed, **Then** the answer is 304 with no body.

---

### User Story 2 - Leadership writes and publishes a lesson (Priority: P1)

A leader creates "Panorama de Gênesis" for 2026 as a draft, fills its sections, then publishes it.
The draft is visible only in the panel until published.

**Why this priority**: without writing, the missing lessons can never be added and errors in the
imported ones can never be fixed.

**Independent Test**: a Liderança user creates a draft with valid content, lists 2026 in the panel
(draft present), reads the public index (draft absent), publishes it and reads the public index
again (present).

**Acceptance Scenarios**:

1. **Given** a Liderança user, **When** they create a lesson with a valid content document, **Then**
   it is stored at the end of its year, `created_by` and `updated_by` are the user, and the answer
   is 201 with the lesson.
2. **Given** a lesson for 2028 and no 2028 year, **When** it is created, **Then** the 2028 year is
   created with an empty theme.
3. **Given** a content document with an unknown block type, an unknown field, an unknown icon, a
   section without blocks, a table row of the wrong width or a comparison with other than two items,
   **When** it is saved, **Then** the answer is 400 `SUNDAY_SCHOOL_CONTENT_INVALID` naming the path
   and the expected shape, and nothing is stored.
4. **Given** a Bible reference whose book, chapter or verse does not exist in every served
   translation, **When** it is saved, **Then** the answer is 400 `SUNDAY_SCHOOL_CONTENT_INVALID`
   naming the offending reference.
5. **Given** a lesson, **When** any field is updated (including `status` and `year`), **Then** the
   change is stored and `updated_by` becomes the user; `created_by` never changes; values for
   `created_by`/`updated_by` in the body are refused as unknown fields.
6. **Given** a lesson moved from 2026 to 2027, **Then** it goes to the end of 2027 and the 2026
   positions close the gap.
7. **Given** a leader, **When** they list a year in the panel, **Then** they get every lesson of that
   year, drafts included, ordered by position.
8. **Given** a Mídia user or a member with no role, **When** they try any panel call, **Then** the
   answer is 403 `PERMISSION_DENIED`; without a token, 401.

---

### User Story 3 - Leadership orders the lessons of a year (Priority: P2)

A leader adds "Panorama de Gênesis" later and drags it before Josué. The other 2026 lessons shift;
2027 is untouched.

**Why this priority**: the missing lessons (Gênesis–Deuteronômio and others) come before the
imported ones in Bible order; without ordering they would sit at the end.

**Independent Test**: with lessons A, B, C in 2026, send the order [C, A, B]; expect positions 0, 1,
2 in that order and every other year unchanged.

**Acceptance Scenarios**:

1. **Given** lessons 7, 42, 3 of 2026, **When** the order of 2026 is set to [3, 7, 42], **Then** they
   get positions 0, 1, 2 in that order, in one transaction.
2. **Given** a list missing a lesson of the year, adding one of another year or repeating one,
   **When** it is sent, **Then** the answer is 400 `SUNDAY_SCHOOL_ORDER_MISMATCH` and nothing
   changes.
3. **Given** a year with no lessons, **When** an order is sent for it, **Then** the answer is 404
   `SUNDAY_SCHOOL_YEAR_NOT_FOUND`.

---

### User Story 4 - Leadership sets the year's theme and deletes lessons (Priority: P3)

A leader sets the 2027 theme and deletes a duplicated lesson.

**Why this priority**: housekeeping; the import already sets the 2026 theme.

**Independent Test**: update the 2027 theme and read it back from the panel; delete a lesson and
check it is gone and the remaining positions are 0..n-1.

**Acceptance Scenarios**:

1. **Given** a year, **When** its theme is updated (blank allowed), **Then** the public index and
   lesson responses show the new theme.
2. **Given** a Liderança user, **When** they delete a lesson, **Then** it is gone and the rest of
   its year close the gap; deleting the last lesson of a year keeps the year row, which simply stops
   appearing publicly.
3. **Given** an unknown year, **When** its theme is updated, **Then** the answer is 404
   `SUNDAY_SCHOOL_YEAR_NOT_FOUND`.

---

### User Story 5 - This year's lessons arrive with the deploy (Priority: P1)

On the deploy's `migrate`, the server gets the 2026 year ("O Drama das Escrituras") and its 18
lessons, published, in Bible order, with only the official dates.

**Why this priority**: without the import the public list is empty on day one.

**Independent Test**: migrate an empty database; expect one year, 18 published lessons with
positions 0..17 in the expected title order, 9 dates set, no teacher, no author; every content
document passes the schema and every reference resolves in every Bible translation; migrate back
and expect the rows gone.

**Acceptance Scenarios**:

1. **Given** an empty database, **When** migrations run, **Then** year 2026 exists with theme "O
   Drama das Escrituras" and 18 published lessons in this order, titled exactly: Josué, Rute,
   2 Samuel, 1 Reis, 2 Reis, 2 Crônicas, Salmos, Provérbios, Isaías, Ezequiel, Daniel, "Obadias,
   Jonas e Miqueias", "Naum, Habacuque e Sofonias", "Ageu, Zacarias e Malaquias", O Período
   Intertestamentário, O Rei Chegou, Mateus, Marcos. A lesson's title is the name of the
   Bible book (or books, joined with commas and "e") it covers; only the two lessons that cover no
   single book keep a descriptive title.
2. **Then** dates are set only for 2 Samuel (2026-05-17), 1 Reis (05-24), 2 Reis (05-31),
   2 Crônicas (06-14), Salmos (07-05), Provérbios (07-12), Isaías (07-26), Ezequiel (08-09) and
   Daniel (08-16); every other lesson has no date. No lesson has a teacher or an author.
3. **Then** every imported section has an icon.

---

### Edge Cases

- **Two lessons with the same title in a year**: allowed; lessons are identified by id.
- **Lesson with no date**: sorted by position like any other; the date is display only.
- **Publishing the first lesson of a new year**: that year becomes the default immediately.
- **Unpublishing the last published lesson of the default year**: the previous published year
  becomes the default; the year disappears from the public list.
- **Moving a lesson to its own year**: no position change.
- **Two leaders appending to the same year at once**: positions may tie; lists order ties by id and
  the next reorder fixes it (same as Bible videos).
- **A user who created lessons is deleted**: the lessons stay, with `created_by`/`updated_by` null.
- **A `**` without a closing pair in text**: stored as written; the app shows unmatched markers as
  plain text.
- **Empty strings in required text fields** (section title, paragraph text, card title...): refused.
- **Year outside a sane range** (before 2000 or after 2100): refused as invalid.

## Requirements *(mandatory)*

### Functional Requirements

**Access**

- **FR-001**: A new panel scope `sunday_school` MUST exist. Admin holds `owner` on it in code;
  Liderança MUST receive `owner` through a data migration whose reverse removes it; Mídia gets
  nothing. Levels come from the method defaults (GET view, POST/PUT/PATCH manage, DELETE owner).
- **FR-002**: Public reads MUST need no sign-in and MUST only ever expose published lessons and
  published years.

**Years**

- **FR-003**: Years MUST be unique by number. Saving a lesson for a year without a row MUST create
  the row with an empty theme.
- **FR-004**: A year's theme MUST be editable (blank allowed); years MUST NOT be created or deleted
  directly through the API.

**Lessons**

- **FR-005**: A lesson MUST hold year, title (non-blank), optional date, optional teacher (free
  text), status `draft`|`published`, position, content, created/updated times and the creating and
  last updating user (null when that user is deleted; null on imported lessons).
- **FR-006**: `created_by`/`updated_by` MUST come from the request user, never from the body.
- **FR-007**: A new lesson, or a lesson moved to another year, MUST go to the end of its year; the
  year it left MUST close the gap. Deleting a lesson MUST close the gap too. Positions in a year are
  0..n-1.
- **FR-008**: Setting the order of a year MUST receive exactly that year's lessons (drafts
  included), each once, and set positions 0..n-1 in the given order in one transaction, touching no
  other year; otherwise 400 `SUNDAY_SCHOOL_ORDER_MISMATCH`.

**Content**

- **FR-009**: Content MUST be validated on every write by a strict schema: unknown fields or block
  types are refused with `SUNDAY_SCHOOL_CONTENT_INVALID` naming the path and the expected shape.
- **FR-010**: A content document MUST have at least one section; a section has a non-blank `title`,
  an optional `icon` and at least one block.
- **FR-011**: The block types MUST be exactly: `paragraph`, `list` (`bullet`|`numbered`|`roman`),
  `key_verse`, `cards`, `comparison` (exactly 2 items, `highlight` flag), `steps`, `table` (every
  row as wide as the header), `stats`, `timeline`, `book_facts` — with the fields of the Contract
  section.
- **FR-012**: Text fields MUST accept `**bold**` and `*italic*` as their only markup; the server
  stores text as given and does not parse it.
- **FR-013**: `key_verse` MUST carry one Bible reference (`proof`); `paragraph`, each `list` item and
  each `cards` item MAY carry `proof_texts[]`.
- **FR-014**: A non-null `reference` MUST name a Bible `abbrev`, and its chapter and every verse MUST
  exist in every served translation; `book_facts.book` MUST be a Bible `abbrev`. Otherwise the write
  MUST be refused with `SUNDAY_SCHOOL_CONTENT_INVALID` naming the offending value.
- **FR-015**: Icons MUST come from a closed list of project names (lowercase snake_case). Any other
  name MUST be refused.
- **FR-016**: For `book_facts`, the chapter count, verse count and the book's position in the Bible
  MUST come from the Bible data and MUST NOT be typed by the editor.

**Public read**

- **FR-017**: The index MUST return the published years (newest first, each with year and theme),
  the default year, and the summaries of the default year's published lessons ordered by position.
  With `year=<n>`, it MUST return the same shape for that year, or 404
  `SUNDAY_SCHOOL_YEAR_NOT_FOUND` when that year has no published lesson. A malformed `year` MUST be
  400.
- **FR-018**: With no published lesson at all, the index MUST answer 200 with no years, a null
  default year and no lessons.
- **FR-019**: A lesson by id MUST return its fields, its year and theme, and its full content, only
  when published; otherwise 404 `SUNDAY_SCHOOL_LESSON_NOT_FOUND`.
- **FR-020**: Public responses MUST support `ETag` / `If-None-Match` with 304 and MUST NOT be marked
  private.

**Panel**

- **FR-021**: The panel MUST list every lesson of a year including drafts (with content), create,
  update (partial), delete and reorder lessons, and update a year's theme. Panel responses MUST NOT
  be cached publicly.

**Initial load**

- **FR-022**: A data migration MUST create year 2026 with theme "O Drama das Escrituras" and the 18
  lessons of User Story 5, published, positions in Bible order, official dates only, no teacher, no
  author. It MUST read frozen JSON files stored beside it, validate them through the same content
  schema, and its reverse MUST remove what it created.
- **FR-023**: The lesson content files MUST be converted by hand from the source PDFs/PPTX and
  reviewed by the user before commit. Every Bible reference in them becomes a `{printed, reference}`
  pair resolved with the doctrine rules.

### Contract

Public (no auth, `ETag`):

```text
GET api/sunday-school/                 index for the default year
GET api/sunday-school/?year=2026       index for 2026
GET api/sunday-school/lessons/<id>/    one published lesson
```

```json
{
  "years": [{"year": 2026, "theme": "O Drama das Escrituras"}],
  "default_year": 2026,
  "year": {"year": 2026, "theme": "O Drama das Escrituras"},
  "lessons": [{"id": 11, "title": "Daniel", "date": "2026-08-16", "teacher": "", "position": 10}]
}
```

Panel (scope `sunday_school`):

| Method and path | Level | Body | Success |
|---|---|---|---|
| `GET api/sunday-school/manage/lessons/?year=2026` | view | — | 200 every lesson of the year, drafts included |
| `POST api/sunday-school/manage/lessons/` | manage | `{year, title, date?, teacher?, status, content}` | 201 lesson |
| `GET api/sunday-school/manage/lessons/<id>/` | view | — | 200 lesson, any status |
| `PATCH api/sunday-school/manage/lessons/<id>/` | manage | any subset of the create fields | 200 lesson |
| `DELETE api/sunday-school/manage/lessons/<id>/` | owner | — | 204 |
| `PUT api/sunday-school/manage/lessons/order/` | manage | `{year, lesson_ids: [...]}` | 204 |
| `GET api/sunday-school/manage/years/` | view | — | 200 every year row (with lesson counts) |
| `PATCH api/sunday-school/manage/years/<year>/` | manage | `{theme}` | 200 year |

Content blocks (all text fields allow inline emphasis; `proof` / `proof_texts[]` items are Bible
references):

| `type` | Fields |
|---|---|
| `paragraph` | `text`, `proof_texts[]`? |
| `list` | `style`: `bullet`\|`numbered`\|`roman`; `items[]`: `{text, proof_texts[]?}` |
| `key_verse` | `label`?, `text`, `proof` |
| `cards` | `items[]`: `{icon?, label?, title, text?, proof_texts[]?}` |
| `comparison` | `items[2]`: `{label, title, text?, highlight}` |
| `steps` | `items[]`: `{label?, title, text?}` |
| `table` | `header[]`, `rows[][]` (same width as header) |
| `stats` | `items[]`: `{value, label}` |
| `timeline` | `events[]`: `{when, text}` |
| `book_facts` | `book` (abbrev), `author`?, `date`?, `style`?, `reading_time`? |

Errors (`{"error_code", "detail"}`):

| Code | Status | When |
|---|---|---|
| `SUNDAY_SCHOOL_YEAR_NOT_FOUND` | 404 | Year absent or (publicly) without published lessons |
| `SUNDAY_SCHOOL_LESSON_NOT_FOUND` | 404 | Unknown id, or draft on the public endpoint |
| `SUNDAY_SCHOOL_CONTENT_INVALID` | 400 | Content breaks the schema, an icon or a Bible reference is invalid |
| `SUNDAY_SCHOOL_ORDER_MISMATCH` | 400 | Order list is not exactly the year's lessons |
| `VALIDATION_ERROR` | 400 | Malformed body, unknown field, bad `year` query |
| `PERMISSION_DENIED` | 403 | Missing scope level |

### Key Entities

- **Sunday school year**: year number (unique), theme (optional), created/updated times.
- **Sunday school lesson**: year, title, date (optional), teacher (optional free text), status,
  position (order inside the year), content document, created/updated times, created by / updated
  by (nullable users).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On the first deploy, a visitor without an account sees the 18 lessons of 2026 under
  the theme "O Drama das Escrituras", in Bible order.
- **SC-002**: Every one of the 18 imported lessons is readable in the app with no PDF, image or
  external link — all content is structured text.
- **SC-003**: A leader can add a missing lesson and place it before the first imported one in two
  actions (create, reorder).
- **SC-004**: A draft is never visible to anyone without the panel scope.
- **SC-005**: Re-fetching an unchanged index or lesson costs no body (304).
- **SC-006**: Every Bible reference served points to a passage that exists in every translation the
  app offers.

## Assumptions

- A year holds a few dozen lessons, so the index is unpaginated.
- A lesson's content stays well under 100 KB; one response per lesson is fine.
- The app renders inline emphasis and draws icons; the server only stores and validates names.
- Converting the 18 lessons is manual work reviewed by the user, like the doctrine files; the
  migration is not committed until that review.

## Out of Scope

- PDF download or showing the original files.
- Images, uploads, an image block.
- Categories or several series in one year.
- Markdown beyond bold/italic, HTML, external links.
- Marking Bible references inside running text.
- Server-side search across lessons.
- Push notifications when a lesson is published.
- The 17 missing lessons (added later through the panel).
