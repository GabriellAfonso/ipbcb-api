# Research: Gallery Trash and Change Feed

Decisions behind [plan.md](plan.md). Each entry: decision, rationale, alternatives rejected.
Code references are to the state after feature 013.

---

## R-01 Where the trash state lives

**Decision**: `Album` and `Photo` gain `deleted_at` (nullable, UTC) and `deletion_batch` (nullable
FK to a new `GalleryDeletionBatch`, `PROTECT`). The batch row holds what the whole action shares:
`id` (UUID), `root_kind` (`album` / `photo`), `root_id`, `deleted_at`, `deleted_by` (FK user,
`SET_NULL`). A row is trashed exactly when `deleted_at` is set; `deletion_batch` is set in the same
statement and cleared with it.

**Rationale**: The trash listing is one entry per batch (spec FR-013), restore works per batch
(FR-017) and the purge works per batch (R-09). With a batch table each of those is a lookup by
key; without one, the root of a batch has to be rediscovered by walking the tree each time. `deleted_at` stays on the rows because it is what every read filters on and what the media
lookup indexes (R-05); copying it from the batch costs one column and saves a join on every
query. `deleted_by` lives only on the batch: one action has one actor.

**Alternatives**:
- *UUID column only, no table*: roots rediscovered as "trashed album whose parent is live or in
  another batch" plus "trashed photo whose album is live or in another batch". Works over the
  small album table, but every trash read and restore repeats the walk, and the actor and time
  get copied onto every row.
- *Stored counts on the batch*: they can never drift (a trashed item cannot change), but a count
  query costs little and keeps one less denormalized value (R-13).
- *`root` as a real FK*: batch → root and root → batch would reference each other, which makes
  the purge's delete order circular. `root_kind` + `root_id` is enough, since the row is always
  read together with the batch.

## R-02 Keeping trashed rows out of every ordinary read

**Decision**: The default manager of both models becomes a live-only manager
(`objects = LiveAlbumManager()`, filtering `deleted_at__isnull=True`). An unfiltered manager,
`all_objects = models.Manager()`, is used only by the trash, restore, purge and media-lookup
repositories. `Meta.base_manager_name` stays Django's plain default, so `photo.album` still loads
a trashed album when the trash code reads one.

The two sibling-name constraints gain `deleted_at__isnull=True` in their conditions:
`(parent, name)` when `parent` is set and the row is live, `(name)` when it is a root and live.

**Rationale**: The feature exists so that deleted photos stop being visible, so the safe default is
to hide them. A live-only default manager covers, without touching them, every 013 repository
query, the reverse relations (`album.photos`, `album.children`), the Django admin changelists,
the admin's parent and album choice fields, and the upload page (it lists albums through
`AlbumService`). An explicit filter in each query would work too, but one forgotten query would
show a trashed photo, and nothing would fail loudly. Code that needs trashed rows has to ask for
them by name (`all_objects`), and a code review can see that.

**Pitfalls handled**:
- A `select_for_update()` through the live manager re-evaluates its `WHERE` after waiting for a
  lock (PostgreSQL EvalPlanQual). An upload that was waiting on an album row while the album was
  being trashed gets **no row** back. `_next_photo_position` and `next_position` ignore the result
  today, so they MUST raise `AlbumNotFoundError` when the lock query returns nothing. Otherwise a
  live photo would be inserted under a trashed album (spec Edge Cases, "Delete races an upload").
- `dumpdata` uses the default manager; database backups are `pg_dump`, which is not affected.

**Alternatives**: explicit `live()` filters in every repository query (rejected above); a
library such as `django-safedelete`: a new dependency for about ten lines of manager code, with
its own idea of cascades that differs from the batch model.

## R-03 Cascade delete and its locking

**Decision**: `GalleryTrashService.delete_album(album_id, actor_id)`, in one transaction:
1. `parent_map(lock=True)` over live albums, which locks every live album row, as 013 moves do
   (R-02 of 013).
2. `subtree_ids(root, parent_map)` (pure, `domain/trash_rules.py`, cycle-safe with a visited
   set): the album and every live descendant.
3. Record the resolved covers before the change (R-06).
4. Insert the batch; `UPDATE` albums in the subtree and live photos whose album is in the subtree
   with `deleted_at=now`, `deletion_batch`, `updated_at=now`, still filtered on live rows, so
   items trashed earlier keep their batch (FR-003).
5. Upsert one deletion mark per trashed album and photo (R-08).
6. Update the ancestors whose resolved cover changed (R-06).
7. One log line (R-14).

`delete_photo` is the same with a one-photo batch and no subtree. It still locks the photo's
album row so it serializes with a concurrent move of the same photo.

**Rationale**: Every tree write of 013 already takes the whole album table's lock, so a delete
cannot interleave with a move or a create under the subtree. Uploads and photo moves lock the
target album row (`_next_photo_position`). With R-02's "no row means 404" they either commit
before the delete, and are trashed with the batch, or fail with `404` afterwards.

**Alternatives**: recursive CTE for the subtree. It would still need the lock, and the album
table is read whole anyway for tree order.

## R-04 Restore

**Decision**: `restore_album(album_id)` / `restore_photo(photo_id)`, in one transaction under the
same album-table lock:
1. Load the item through `all_objects`. It must be trashed and be the root of its batch
   (`batch.root_kind`/`root_id`). Otherwise raise `TrashEntryNotFoundError` → `404` (FR-019). A
   purged item has no row, so it gets the same `404`.
2. Check that the parent (album) or the photo's album is live. Otherwise raise
   `TrashedParentError(kind, item_id, parent_album_id)` → `400` (FR-022).
3. Album only: check whether a live sibling holds the name. If one does, raise
   `AlbumRestoreNameConflictError(album_id, name, sibling_id)` → `400` (FR-021). The partial
   unique constraint still catches a concurrent create; its `IntegrityError` is translated to the
   same error.
4. `UPDATE` every row of the batch: `deleted_at=NULL`, `deletion_batch=NULL`, `updated_at=now`.
   Positions are untouched (FR-018).
5. Delete the marks of those rows (FR-020), delete the batch row, update the ancestors whose
   resolved cover changed, and log.

Only the root can conflict, because nothing can be written under a trashed album (spec
Assumptions), so steps 2–3 check the root alone.

**Messages**: Portuguese, since they reach the management panel. Example: `"Não é possível
restaurar o álbum 7 ('Culto'): o álbum 12 já usa esse nome no mesmo lugar. Renomeie-o antes."`
and `"Não é possível restaurar a foto 301: o álbum 7 está na lixeira. Restaure o álbum
primeiro."`. `extra_context` carries `album_id`/`photo_id`, `name`, `conflicting_album_id` or
`trashed_parent_id`.

## R-05 Media check: hiding trashed files without coupling features

**Decision**:
- `features/media` declares the port it needs, a Protocol `TrashedMediaLookup` with
  `is_trashed(relative_path: str) -> bool`, in `features/media/repositories/interfaces.py`.
- `features/gallery` implements it as `GalleryTrashedFileLookup`
  (`repositories/trashed_file_lookup.py`). Protocols are structural, so it imports nothing from
  `media`.
- `config/di.py`, which already knows both features, injects it into `MediaAccessService`. The
  rule "features never import each other" holds.
- The lookup is **one query**: a `UNION ALL` of
  `Photo.all_objects.filter(deleted_at__isnull=False).filter(Q(image=p) | Q(thumbnail=p))` and
  `Album.all_objects.filter(deleted_at__isnull=False, cover_image=p)`, limited to 1.
  Three **partial indexes** make it exact and tiny: `image`, `thumbnail` and `cover_image`, each
  `WHERE deleted_at IS NOT NULL`. Only trashed rows are indexed: tens of rows, whatever the
  gallery's size. Both PostgreSQL and SQLite support partial indexes.
- The stored file name *is* the media path (`gallery/7/9b1e….jpg`, and pre-013
  `gallery/retiro-2025/IMG_0042.jpg`), and 009 hands the service the path decoded exactly once.
  An equality match therefore covers old and new paths alike (FR-027).
- `MediaViewer` gains `can_own_gallery`, computed by the view from
  `scope_permission(Scope.GALLERY, {"GET": Level.OWNER})`, the same way it computes
  `can_view_members`.

**Decision flow for `gallery/`**, which keeps 009's order: path → folder rule → permission →
(trash) → existence:

| Caller | Lookup? | Trashed file | Live file |
|--------|---------|--------------|-----------|
| member + owner | no | served | served |
| member, not owner | yes | `404` (`MediaFileTrashedError`) | served |
| owner, not member | yes | served | `403` (009 rule unchanged) |
| neither | no | `403` | `403` |

Members who are also owners skip the query entirely, so the usual gallery request costs no
extra query when an owner makes it, and one indexed probe of a tiny index when a member does.
`MediaFileTrashedError` subclasses `MediaFileNotFoundError`, so the response is the ordinary
`404`. The decision log gets a new outcome, `trashed`, logged with the folder only, as usual.

**Alternatives**:
- *Two queries* (photo, then album): simpler SQL, but breaks "one query".
- *Choosing the table by path shape* (`gallery/covers/…` → album): a pre-013 album named "Covers"
  has legacy files at `gallery/covers/<file>`, so the shape is not reliable.
- *Moving trashed files to a non-served folder*: the move is not transactional with the row, a
  failure leaves the two disagreeing, and restoring means moving the file back. It would also
  break the "files never move" rule of 013.

## R-06 `updated_at` and derived changes

**Decision**: `updated_at` (`DateTimeField`, indexed, `default=timezone.now`) on both models, set
explicitly to `clock.now()` by every repository write. The repositories receive the project
`Clock` through their constructor (DI already has a `clock` singleton), so tests control time.
`auto_now` is not used, because `QuerySet.update()`, which every 013 write uses, ignores it.

Derived changes (spec FR-034), each bumped where it happens:

| Change | Rows bumped |
|--------|-------------|
| album rename | the album + every live photo in it (`album_name`) |
| album move, create, trash, restore, cover replace/remove/automatic, album reorder | every album whose **resolved cover** changed, plus the album itself |
| album or photo reorder | only the rows whose `position` changed |
| photo edit or move, thumbnail backfill | the photo |

Resolved-cover changes are computed exactly, not guessed: the service reads the live records
before the write and again after it, inside the same transaction, and
`changed_cover_albums(before, after)` (pure, `domain/album_tree.py`) returns the albums whose
resolved cover *file* differs. It compares the resolved cover name, not the source id, so
replacing an own cover (same source, new file) counts. The album table is small and already read
whole by these operations, so this costs one extra read per tree write.

**Alternatives**: bumping every ancestor on any cover change (simpler, over-reports); computing
derived changes at read time with joins (fragile, and it cannot express "the resolved cover of X
changed because a sibling of its first child was reordered").

## R-07 Feed cursor

**Decision**: The cursor is an opaque string `v1.<base64url of the read's start instant in
microseconds>`, issued by the server. A read with cursor *t* returns rows with
`updated_at > t − CURSOR_OVERLAP` and marks with `deleted_at > t − CURSOR_OVERLAP`, where
`CURSOR_OVERLAP = 90 s` (clarified with the requester: overlap, not delay). The new cursor is the
instant the read started, taken from the clock before the queries run.

- No `since`: full sync, every live album and photo, `full_sync_required: false`.
- `since` unreadable, from another version, in the future (beyond `CURSOR_OVERLAP`), or older
  than `MARK_RETENTION − CURSOR_OVERLAP`: empty lists, `full_sync_required: true`, new cursor.
- Albums in the answer carry resolved covers, so the service builds views from the whole live
  album table (as `list_albums` does) and keeps the changed ones, in tree order. Photos: one query
  filtered on `updated_at`, ordered like `GET /api/photos/`.

**Why an overlap**: A row's `updated_at` is taken before its transaction commits. A feed read
that runs between the two would not see the row, and the next read, starting at that cursor,
would skip it. That is the miss FR-038 forbids. Every write that sets `updated_at` runs inside a
request (gunicorn `--timeout 60`) or in a short per-row transaction of a management command, so
no transaction outlives 60 s. A 90 s overlap therefore re-reads anything that could have
committed late. The price is duplicates for items changed in the last 90 s, which the app applies
idempotently. SC-006 is amended accordingly (spec, Clarifications).

**Unsigned on purpose**: a forged cursor can only make a member receive gallery data they can
already read in full. The format is versioned (`v1.`) so it can change later; an unknown version
answers `full_sync_required`.

**Alternatives**: a delay instead of an overlap (no duplicates, but changes show up ~90 s late;
rejected by the requester); an auto-increment change log (ids are also allocated before commit,
so the same gap exists); PostgreSQL snapshot ids (`pg_current_snapshot`), which are exact but
PostgreSQL-only, while tests run on SQLite.

## R-08 Deletion marks

**Decision**: `GalleryDeletionMark(kind, object_id, deleted_at)`, unique on `(kind, object_id)`,
indexed on `deleted_at`. A delete upserts one mark per trashed row
(`bulk_create(update_conflicts=True, unique_fields=[kind, object_id],
update_fields=[deleted_at])`, supported on PostgreSQL and SQLite), so an id deleted, restored and
deleted again keeps one mark with the latest date. A restore deletes the marks of the rows it
brings back. Row purges never touch marks. Marks older than `MARK_RETENTION` (90 days) are deleted
by the daily command, in a step separate from the row purge (spec FR-033, clarified).

No FK to the rows: a mark has to outlive its row.

## R-09 Purge

**Decision**: `GalleryPurgeService.purge_expired()`, called by the command
`purge_gallery_trash`:
1. Read the ids of batches with `deleted_at < now − TRASH_RETENTION`, oldest first.
2. For each batch, in **its own transaction**:
   - collect the file names (`image`, `thumbnail`, `cover_image`) of its rows;
   - delete its photos, then its albums deepest first (`purge_order`, pure: sorts the batch's
     albums by depth within the batch), then the batch row;
   - `transaction.on_commit(robust=True)` deletes each file. `default_storage.delete` of a missing
     file is a no-op (FR-033).
3. A batch that raises (e.g. `ProtectedError`) is rolled back, reported as skipped with its id
   and error type, and the run goes on.
4. Delete expired marks (R-08).
5. Return a `PurgeReport` (batches, albums and photos purged; skipped batch ids; marks expired).
   The command prints it as a plain line and exits `0`, even when some batches were skipped, so
   a scheduler does not retry forever. Skips are in the log (R-14).

**`Photo.album` becomes `PROTECT`** (from `CASCADE`). With `CASCADE`, deleting an album would
also delete, without a trace, any photo row of an *older* batch whose own purge had failed,
orphaning its files. With `PROTECT` the album purge fails instead, gets reported, and is retried
the next day after the photo goes. No code path deletes an album with photos any more: the API
has no hard delete and the admin delete is disabled (R-12).

**Order across batches**: a descendant trashed on its own is older than its parent's batch, so
oldest-first purges it first. A live row never sits under a trashed album (R-02, R-03), so a
purged album never has a live child.

## R-10 Scheduling the purge

**Decision**: a daily host cron entry on the production server, outside this repository, like
the nginx configuration:

```
30 3 * * * docker exec ipbcb-server-prod python manage.py purge_gallery_trash
```

It is recorded in the plan's Dependencies and in quickstart §6. The command is idempotent, so a
missed or doubled run is harmless: the next run catches up.

**Alternatives**: a scheduler inside the app container (celery beat, APScheduler). That adds a
dependency and a process for one daily job, and with 4 gunicorn workers each would start its own
scheduler.

## R-11 Endpoints and permissions

- `DELETE` added to `AlbumDetailAPIView` and `PhotoDetailAPIView`: `GALLERY_WRITE`, whose default
  level for `DELETE` is `owner`.
- `TrashListAPIView`, `AlbumRestoreAPIView`, `PhotoRestoreAPIView`:
  `[IsAuthenticated, scope_permission(Scope.GALLERY, {"GET": Level.OWNER, "POST": Level.OWNER})]`.
  012 allows overrides that raise the level; `validate_overrides` checks it at import.
- `GalleryChangesAPIView`: `[IsMemberUser]`, like the other gallery reads.
- `since` is read from `request.query_params` as a plain string and handed to the service
  unparsed. Decoding it is the domain's job (R-07), and a bad value is not an error.

## R-12 Django admin

**Decision** (clarified with the requester): deleting is disabled in both admins,
`has_delete_permission` returns `False`, which also removes the bulk "delete selected" action.
The live-only default manager (R-02) keeps trashed albums out of the album changelist, the
parent field and the photo's album field. The upload page lists albums through `AlbumService`,
which now reads live rows only.

**Alternatives**: routing `delete_model` and `delete_queryset` through the trash service. The
Django confirmation page would still list a hard cascade of rows that does not happen, and it
would add a second deletion UI to test.

## R-13 Trash listing

**Decision**: one query for the batches, most recent first, with `select_related("deleted_by")`,
and two annotated subqueries: the count of albums in the batch other than the root, and the
count of photos in the batch. Two more queries load the roots by id (albums, and photos with
`select_related("uploaded_by")`), both through `all_objects`. Four queries in total, whatever
the size of the trash.

Display names: `user.get_full_name() or user.username` (`accounts.User` is an `AbstractUser`),
`null` when the FK is `NULL`. `thumbnail_url`: the photo's thumbnail, or the album's own cover.

## R-14 Logging

`features.gallery` logger, spec 002 JSON, one line per event:

| Event | Fields |
|-------|--------|
| `gallery_trashed` | `kind`, `id`, `batch`, `actor_id`, `album_count`, `photo_count` |
| `gallery_restored` | same |
| `gallery_purged` | same, `actor_id: null` |
| `gallery_purge_skipped` | `batch`, `error` (exception type only) |
| `gallery_purge_summary` | `batches`, `albums`, `photos`, `skipped`, `marks_expired` |

Names, captions and paths are never logged: ids only.

## R-15 Migration

`makemigrations gallery` → `0004_…`: `deleted_at`, `deletion_batch` and `updated_at` on both
models; the `GalleryDeletionBatch` and `GalleryDeletionMark` models; the two unique constraints
replaced by their live-only versions; three partial indexes plus the `updated_at` indexes;
`Photo.album` to `PROTECT`. `updated_at` gets `timezone.now` for existing rows. Any value works,
because every app starts with a full sync, so **no data migration is needed**.

Generated, not hand-written, so the §5 compensating controls do not apply. Quickstart §3 still
runs it forward and back on a restored production dump, because it replaces constraints on a
populated table.

## R-16 Resources gain `position`

`AlbumView`, `PhotoView`, `AlbumSerializer` and `PhotoSerializer` gain `position` (clarified).
Every endpoint returning the resources gets it, the 013 write responses included. The field is
additive and appended last, so old clients ignore it.
