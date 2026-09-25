# Data Model: Protected Media Access

No database change. No model, no migration. Everything below is an in-memory type in
`server/features/media/` or an addition to `core/`.

---

## MediaAudience (enum)

Who a folder is readable by.

| Value    | Satisfied when              | Read through                          |
|----------|-----------------------------|---------------------------------------|
| `MEMBER` | `MediaViewer.is_member`     | `core.http.permissions.IsMemberUser`  |
| `LEADER` | `MediaViewer.is_leader`     | `core.http.permissions.IsAdminUser`   |

`LEADER` does not imply `MEMBER`, and `MEMBER` does not imply `LEADER` (spec, Assumptions).

## Folder rules (constant)

A fixed mapping, first path segment → audience. Exact, case-sensitive match.

| Folder     | Audience |
|------------|----------|
| `gallery`  | `MEMBER` |
| `profiles` | `MEMBER` |
| `members`  | `LEADER` |

A folder absent from the table has no audience: every request for it is `unruled` (404).
Adding a folder is a code change plus a spec change — never configuration.

## MediaViewer (Pydantic DTO, `StrictBaseModel`)

What the service knows about the caller. Built by the view; the service never sees `request`.

| Field       | Type | Source                                                 |
|-------------|------|--------------------------------------------------------|
| `is_member` | bool | `IsMemberUser().has_permission(request, view)`         |
| `is_leader` | bool | `IsAdminUser().has_permission(request, view)`          |

## MediaFile (Pydantic DTO, `StrictBaseModel`)

The outcome of a successful `authorize`.

| Field            | Type  | Meaning                                                        |
|------------------|-------|----------------------------------------------------------------|
| `relative_path`  | str   | The validated requested path, verbatim — used for the redirect |
| `absolute_path`  | Path  | Resolved location on disk — used only by the development mode  |
| `content_type`   | str   | From the extension allow-list (research R-08)                  |

## MediaAccessOutcome (enum) — log only

`allowed`, `forbidden`, `not_found`, `rejected`, `unruled`. Written to the decision log with
the folder (research R-09); never returned to the client.

---

## Validation rules (research R-04)

A requested path is **valid** when all hold:

1. non-empty, does not start with `/`;
2. has at least two segments when split on `/`;
3. no segment is empty, `.` or `..`;
4. contains no `\`, no `%`, no character `< 0x20` and no `0x7f`.

Validation never rewrites the path.

## Decision sequence (service `authorize`)

```text
validate path ──invalid──▶ MediaPathRejectedError        (404, outcome=rejected)
     │
first segment in rules? ──no──▶ MediaFolderNotRuledError (404, outcome=unruled)
     │
viewer satisfies audience? ──no──▶ MediaAccessDeniedError (403, outcome=forbidden)
     │
repository.locate(path) is None? ──yes──▶ MediaFileNotFoundError (404, outcome=not_found)
     │
MediaFile                                                 (200, outcome=allowed)
```

## Domain exceptions (added to `core/domain/exceptions.py`)

| Class                       | Base                    | `error_code`        | HTTP |
|-----------------------------|-------------------------|---------------------|------|
| `PermissionDeniedError`     | `DomainError`           | `PERMISSION_DENIED` | 403  |
| `MediaAccessDeniedError`    | `PermissionDeniedError` | `PERMISSION_DENIED` | 403  |
| `MediaPathRejectedError`    | `NotFoundError`         | `NOT_FOUND`         | 404  |
| `MediaFolderNotRuledError`  | `NotFoundError`         | `NOT_FOUND`         | 404  |
| `MediaFileNotFoundError`    | `NotFoundError`         | `NOT_FOUND`         | 404  |

The three 404 classes carry the same message template, so their responses are identical.

## Settings (added to `config/settings/base.py`)

| Setting                     | Value                        |
|-----------------------------|------------------------------|
| `PROTECTED_MEDIA_LOCATION`  | `"/ipbcb/protected-media/"`  |
| `DEFAULT_THROTTLE_RATES["media"]` | `"3000/hour"` (test: `"99999/min"`) |
