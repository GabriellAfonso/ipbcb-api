# Feature Specification: Gallery Videos

**Feature Branch**: `023-gallery-videos`

**Created**: 2026-10-26

**Status**: Draft

**Input**: User description: "Add videos to the gallery." (full request — current state, what to
build, out-of-scope list and four open decisions — in `../TODO/specify_gallery_videos_backend.md`,
decided in conversation `75f3ece2-ae36-412f-847c-4fd2bf68030b` of 2026-10-26.)

## Context

The gallery holds only photos. The media team also records short videos (typically 30 seconds to a
few minutes) at church events, and members should see them inside the same albums as the photos.

The guiding decision of the whole feature is **simplicity: the server never transcodes or inspects
video content**. The media team posts files that are small and playable; the server stores the file
exactly as sent and serves it. The uploader's phone makes the poster image and reads the duration,
and checks codecs, before sending. (The user first considered server-side compression and dropped
it: "quem tem que comprimir é a pessoa da mídia".)

A video is a gallery item like a photo: it is stored as a `Photo` row with a media type of
`video`. The model, the table and the endpoints keep their names, because tags, trash, purge,
ordering, move, the change feed and the app's whole sync already work on `Photo`; a separate model
would duplicate all of it.

This spec covers the backend and the nginx configuration. The Android app is a separate spec that
depends on this one (`../TODO/specify_gallery_videos_app.md`).

### Relation to other specs

- **`specs/gallery/spec.md`** — the domain spec; `Photo` gains `media_type`, `duration_ms` and
  `file_size`, `POST /api/photos/` gains the video upload, and the resource gains three fields.
- **`specs/013-gallery-write-api/`** — the photo upload, its derivatives and the automatic first
  cover, reused for the poster.
- **`specs/014-gallery-trash-sync/`** — trash, restore, purge and change feed, unchanged and valid
  for videos.
- **`specs/015-gallery-member-tags/`** — tags, valid for videos.
- **`specs/016-photo-upload-idempotency/`** — the client upload id, mandatory for a video.
- **`specs/009-protected-media-access/`** — the media check that serves the files; its content type
  allow-list gains MP4 and MOV.
- **`specs/001-api-error-handling/`** — every refusal uses its canonical error shape.

## Clarifications

### Session 2026-10-26

Decided in the design conversation (see Input):

- Q: Compress or transcode on the server? → A: Never. No ffmpeg/ffprobe on the server; the media
  team posts files that are already small.
- Q: Limits? → A: 100 MB per video file, no duration limit ("sem limite de tempo, só de MB").
- Q: Formats? → A: MP4 and MOV only. MKV dropped: it often carries AC3/DTS audio that many Android
  phones cannot play ("quero mais problemas não").
- Q: Poster and duration? → A: Made on the uploader's phone and sent with the video; both required.
  A video without poster never exists.
- Q: Who uploads? → A: whoever uploads photos today (scope `gallery`, `manage`).
- Q: Tags, trash, move, cover for videos? → A: Yes, all as for photos; a cover from a video uses its
  poster.
- Q: Chunked or resumable upload? → A: No. One request; the client upload id makes a retry safe.
- Q: Old app versions receiving videos as if they were photos? → A: Accepted.
- Q: `file_size` for existing photos? → A: Filled by a one-off command ("preenchido por um comando
  único").

Open decisions of the request, resolved with their recommendations (the user delegated them:
"se tiver dúvidas pergunta pro chat em que eu decidi"):

- Upload field names: separate `video` and `poster` fields plus `duration_ms`; `image` keeps
  meaning "photo".
- The stored original of a video never goes through image decoding anywhere (admin, validators,
  backfill commands).
- `date_taken` of a video: optional, sent by the app from the video metadata, same format as the
  photo field.
- `file_size` backfill: an idempotent management command, run once in production.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Media team uploads a video (Priority: P1)

A media team member picks a short MP4 recorded at the retreat and sends it to the album "Retiro
2026". The phone makes the poster and reads the duration; the server stores the video as sent and
the poster as its thumbnail, and the video appears in the album among the photos.

**Why this priority**: Without upload there are no videos to show.

**Independent Test**: Send a valid MP4 with a poster, a duration and a client upload id to an
album; the response lists one item of media type `video` with its duration, size, video URL and
poster URL.

**Acceptance Scenarios**:

1. **Given** an album and a user with `manage` on `gallery`, **When** they send an MP4 of 40 MB
   with a JPEG poster, `duration_ms` 45000 and a client upload id, **Then** the answer is `201`
   with one accepted item: `media_type` `video`, `duration_ms` 45000, `file_size` equal to the
   bytes sent, `image_url` pointing to the stored `.mp4` and `thumbnail_url` to a poster at most
   1000 px on its longest side; the item is last in the album.
2. **Given** the same request with a MOV file, **Then** it is accepted and stored with `.mov`.
3. **Given** a file of 100 MB + 1 byte, **Then** it is refused with `400` and a Portuguese reason
   naming the size and the 100 MB maximum; nothing is stored.
4. **Given** an MKV, WEBM or AVI file (whatever its name or declared type), or an MP4 renamed
   from any other content, **Then** it is refused with `400` and a Portuguese reason saying only
   MP4 and MOV are accepted.
5. **Given** a request without poster, without `duration_ms`, or with an invalid poster, **Then**
   it is refused with `400` and nothing is stored.
6. **Given** an album with no items and no own cover, **When** the first item uploaded is a video,
   **Then** the album's cover is made from the video's poster.
7. **Given** a retry with the same client upload id after the first answer was lost, **Then** the
   answer is `201` with the video already stored, and nothing new is stored; if that video is in
   the trash, the answer is `409`.

---

### User Story 2 - Members see and download videos (Priority: P1)

A member opening the gallery gets videos in the same lists and change feed as photos, can tell
them apart, knows their duration and size before downloading, and downloads the file with the
same authentication as photos, resuming an interrupted download.

**Why this priority**: The whole point of the feature; it shares P1 with upload because each is
useless without the other.

**Independent Test**: With one photo and one video stored, list the album and read the change
feed; request the video file with a member token and a `Range` header.

**Acceptance Scenarios**:

1. **Given** a photo and a video in an album, **When** a member lists the album, all photos or the
   change feed, **Then** both appear in the same list and order, the photo with `media_type`
   `photo`, `duration_ms` `null` and its `file_size`, the video with `media_type` `video`, its
   `duration_ms` and `file_size`.
2. **Given** a member token, **When** the app requests the video URL, **Then** the file is served
   with content type `video/mp4` (or `video/quicktime` for MOV); without member access it is
   refused as any gallery file is.
3. **Given** a request for the video with `Range: bytes=1000-`, **Then** production answers `206`
   with `Content-Range` and the bytes from offset 1000.

---

### User Story 3 - Videos behave as photos everywhere else (Priority: P2)

A manager tags members in a video, moves it to another album, reorders it, edits its name,
description and date, deletes it and restores it; the purge removes the video file and its poster;
a manager can make a video's poster the album cover.

**Why this priority**: Decided by the user, and almost free since a video is a `Photo` row; it
still needs to be verified.

**Independent Test**: Run every existing photo operation on a stored video.

**Acceptance Scenarios**:

1. **Given** a video, **When** a manager tags a member in it, **Then** the member filter returns it
   and the change feed reports it.
2. **Given** a video, **When** it is deleted, **Then** it goes to the trash, its file and poster
   answer `404` to members without `owner`, and it can be restored; after 30 days the purge removes
   the row, the video file and the poster.
3. **Given** a video, **When** a manager moves it, reorders it or edits its name, description or
   `date_taken`, **Then** it behaves exactly as a photo would; its media type, duration and size
   never change.
4. **Given** the poster image of a video, **When** the app sends it to `PUT /api/albums/{id}/cover/`,
   **Then** the album gets it as its own cover (no change to that endpoint).

---

### User Story 4 - Sizes of existing photos are known (Priority: P3)

The app shows storage totals ("Fotos 320 MB · Vídeos 1,2 GB") for files it has not downloaded, so
every photo already stored gets its size once.

**Why this priority**: Only affects totals shown in settings; new uploads already carry it.

**Independent Test**: Run the backfill command on photos without size; run it again.

**Acceptance Scenarios**:

1. **Given** photos stored before this feature, **When** the backfill command runs, **Then** each
   photo whose original exists gets `file_size` equal to the file's bytes, and the change feed
   reports it as changed.
2. **Given** a photo whose original file is missing, **Then** its `file_size` stays `null` and the
   command lists its id; the others are filled.
3. **Given** the command already ran, **When** it runs again, **Then** nothing changes.

### Edge Cases

- **Both `image` and `video` in one request**: `400`, nothing stored. A request is a photo upload
  or a video upload, never both.
- **Two video files in one request**: `400` naming the count; one video per request.
- **Video without client upload id**: `400`. The app always sends one, and a 100 MB file must never
  be stored twice by a retry.
- **`duration_ms` zero, negative, not an integer or sent twice**: `400` naming the value and the
  expected shape.
- **`date_taken` not a `YYYY-MM-DD` date**: `400`. Absent or empty means `null`.
- **Poster larger than 10 MB, not JPEG/PNG/WEBP/GIF, or above 50 MP**: the video is refused with
  the poster's reason, and nothing is stored.
- **A video file that starts with a valid `ftyp` box but is truncated or carries a codec phones
  cannot play**: accepted. The server checks the container signature only; the app checks codecs.
- **Unknown album**: `404`, as for photos; a repeat of a stored client upload id never looks the
  album up (spec 016).
- **Writing the row fails after the files were stored**: the video file and the poster are deleted;
  nothing remains.
- **Automatic cover from the poster fails**: logged, never raised; the video stays (as for photos).
- **Thumbnail backfill (`generate_photo_thumbnails`)**: never reads a video, even one without
  thumbnail; a video's original is never decoded as an image.
- **Django admin**: a video's page shows its file as a link, never decodes it; the admin upload
  page stays photos only.
- **`PATCH` with `media_type`, `duration_ms` or `file_size`**: `400` like any other key not
  editable.
- **Old app versions**: receive videos in the photo lists and treat them as photos; accepted.

## Requirements *(mandatory)*

### Functional Requirements

**Stored data**

- **FR-001**: Every gallery item MUST have a media type, `photo` or `video`. Every item stored
  before this feature is a `photo`.
- **FR-002**: A video item MUST store its original file exactly as sent, under
  `gallery/{album_id}/{uuid}.{mp4|mov}`, and its poster as the item's thumbnail.
- **FR-003**: A video item MUST store its duration in milliseconds (positive integer); a photo's
  duration is `null`.
- **FR-004**: Every item uploaded from now on, photo or video, MUST store the size in bytes of its
  original file. Items stored before this feature have no size until the backfill (FR-024) runs.
- **FR-005**: The stored original of a video MUST never be decoded as an image anywhere: upload,
  admin, backfill commands, cover generation.
- **FR-006**: Media type, duration and size MUST never change after upload; the `PATCH` endpoint
  keeps refusing them as non-editable keys.

**Resource**

- **FR-007**: The Photo resource MUST gain, after `members` and in this order, `media_type`,
  `duration_ms` and `file_size`. Every existing field keeps its name, meaning and order. The same
  resource is returned by the two photo lists, the change feed, the upload, `PATCH` and the tag
  endpoints.
- **FR-008**: For a video, `image_url` MUST be the URL of the video file and `thumbnail_url` the
  URL of the poster.

**Upload**

- **FR-009**: `POST /api/photos/` MUST accept a video upload with the same permission as photos:
  multipart fields `album_id`, `video` (exactly one file), `poster` (exactly one image),
  `duration_ms`, `client_upload_id` (all required) and `date_taken` (optional, `YYYY-MM-DD`).
- **FR-010**: A request carrying both `image` and `video` MUST be refused with `400`; a request
  carrying neither keeps today's "send at least one file" refusal.
- **FR-011**: Request shape checks (FR-009, FR-010, the client upload id shape of spec 016) MUST
  come after the permission and before any lookup; then a repeat of a stored client upload id MUST
  answer as spec 016 does (`201` with the live item, `409` for a trashed one), without examining or
  storing anything.
- **FR-012**: The video file MUST be at most **100 MB** (104 857 600 bytes), one constant, checked
  from the upload's size before its bytes are read.
- **FR-013**: The video format MUST be detected from the file's first bytes, never from its name or
  declared content type: an ISO base media `ftyp` box whose brand is QuickTime (`qt  `) is MOV, any
  other `ftyp` brand except the ones of other formats (3GPP `3gp*`/`3g2*`, audio-only
  `M4A `/`M4B `/`M4P `/`F4A `/`F4B `, HEIF/AVIF and JPEG 2000 images) is MP4; a QuickTime file starting with a classic `moov`, `mdat`, `wide`, `free` or `skip` atom is
  MOV. Anything else — MKV, WEBM, AVI, images — MUST be refused with a Portuguese reason saying
  only MP4 and MOV are accepted. The stored extension is `mp4` or `mov` accordingly.
- **FR-014**: The server MUST NOT check codecs, resolution or duration of the video.
- **FR-015**: The poster MUST pass the same validation as a photo (10 MB, JPEG/PNG/WEBP/GIF,
  50 MP) and become the item's thumbnail through the photo thumbnail derivative (longest side
  1000 px, JPEG 85). An invalid poster refuses the whole upload.
- **FR-016**: An accepted video MUST get `name` = the video's filename (cut as for photos), empty
  `description`, `date_taken` = the value sent or `null`, the last position in its album, the
  uploader recorded and the client upload id stored.
- **FR-017**: When the album has no live items and no own cover at the moment of the upload, the
  accepted video MUST give it its automatic cover, made from the poster exactly as from a photo.
- **FR-018**: The video file and the poster MUST be written before the row and deleted if the row
  cannot be written.
- **FR-019**: An accepted video MUST answer `201` with `{"accepted": [<item>], "rejected": []}`; a
  refused video file or poster (size, format, decoding, pixels) MUST answer `400`
  `VALIDATION_ERROR` with the detail "O vídeo não foi aceito." and `rejected` listing the video's
  filename with the reason, as an upload whose every photo was rejected does.
- **FR-020**: Photo upload MUST keep working unchanged, apart from recording `file_size` and the
  media type `photo`.
- **FR-021**: The Django admin upload page MUST stay photos only.

**Serving**

- **FR-022**: The media check MUST serve `.mp4` as `video/mp4` and `.mov` as `video/quicktime`,
  with the same access rules, trashed-file rule and `Cache-Control: private, no-cache` as every
  gallery file.
- **FR-023**: In production, a `Range` request for a video MUST be answered `206` with
  `Content-Range` (nginx, after the media check); the upload path MUST accept a body of up to
  110 MB at `/ipbcb/` and buffer it before it reaches the application server.

**Backfill and commands**

- **FR-024**: A management command MUST fill `file_size` of every item whose size is unknown from
  its stored original; a missing file leaves it `null` and is listed in the output. It MUST be
  idempotent, and each filled item MUST count as changed for the change feed.
- **FR-025**: `generate_photo_thumbnails` MUST skip videos.

**Unchanged for videos**

- **FR-026**: Tags, member filter, trash and restore, purge (removing the video file and the
  poster), move, reorder, `PATCH` of name/description/date, change feed and the album cover from an
  uploaded poster image MUST work for videos exactly as for photos.

### Key Entities

- **Gallery item (`Photo`)**: a photo or a video in an album. Gains media type (`photo`/`video`),
  duration in milliseconds (videos only) and original file size in bytes (every item). For a video,
  the original is the video file and the thumbnail is the poster.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A media team member can publish a video of up to 100 MB into an album with one
  request, and every member sees it in that album on their next sync.
- **SC-002**: 100% of stored videos have a poster, a duration and a size; no video without poster
  can be created by any path.
- **SC-003**: 100% of non-MP4/MOV files are refused with a reason the uploader can act on,
  whatever their name or declared type.
- **SC-004**: An interrupted video download resumes from where it stopped instead of starting
  over.
- **SC-005**: After the one-off backfill, every photo whose original exists has a known size, so
  the app can show storage totals without downloading anything.
- **SC-006**: Every existing photo operation (tags, trash, restore, purge, move, order, edit,
  change feed) works on a video with no video-specific step for the manager.

## Assumptions

- The uploader's phone produces the poster (JPEG) and the duration, checks the codecs, and never
  sends a video without them (app spec).
- Videos are short and already compressed by the media team; no server-side processing is needed.
- nginx (`nginx-deploy`, commit `c954a67`) already allows 110 MB at `/ipbcb/`, buffers request
  bodies and answers `Range` on the protected media location; only the end-to-end check remains.
- The application server receives a request only once nginx has buffered its whole body, so a slow
  mobile upload never holds a worker.
- Django streams uploads above its in-memory limit to a temporary file; no setting caps the body
  below 110 MB (file parts do not count toward `DATA_UPLOAD_MAX_MEMORY_SIZE`).
- Old app versions showing videos as broken photos is accepted.

## Out of Scope

- Any transcoding, compression, resolution change or codec inspection on the server.
- HLS or adaptive streaming; the app plays only fully downloaded files.
- A duration limit.
- Video upload from the Django admin page.
- Chunked or resumable upload.
- A media type on trash entries (the trash shows a video's poster as its thumbnail).
