# Quickstart: Edit and Delete Songs

## Run the tests

From `server/`, with `.venv_windows` active:

```powershell
# during the feature: the songs domain plus the access matrix
pytest features/songs core/tests/integration/test_management_access_matrix.py

# before shipping: the whole suite
pytest
```

## What proves each requirement

| Scenario | Where | Expected |
|----------|-------|----------|
| Edit each field alone, clear link, empty body, unknown key, `null`, duplicate, self/case-only | unit, `SongService` + `SongChangesInput` | per [contract](contracts/song-detail-api.md) |
| `NewSongInput` behaviour unchanged after the shared-type refactor | `tests/unit/test_new_song_input.py`, unmodified | green |
| Delete free song; blocked by plays / setlist / both; unknown id | unit, `SongService` with a named fake repository | `204` / `409` message and data per contract / `404` |
| Late `ProtectedError` becomes `409`, nothing deleted | integration, real DB | `409`, song + plays intact |
| Late `IntegrityError` becomes `409`; unrelated `IntegrityError` re-raised | unit, named fake | as stated |
| Chord charts + lyrics removed with the song | integration | rows gone |
| Plays and setlists untouched after a blocked delete | integration | counts unchanged |
| Old ETag after an edit on `songs`, `songs-by-sunday`, `top-songs` | integration | `200`, not `304` |
| `401` / `403 view` / `PATCH manage` / `DELETE 403 manage`, `owner` ok | integration + access matrix rows | as stated |

## Manual check (dev server)

```powershell
$h = @{ Authorization = "Bearer <manage token>"; "Content-Type" = "application/json" }
Invoke-RestMethod -Method Patch -Uri http://localhost:8000/ipbcb/api/songs/1/ -Headers $h -Body '{"title":"Oceans"}'
Invoke-RestMethod -Method Delete -Uri http://localhost:8000/ipbcb/api/songs/1/ -Headers @{ Authorization = "Bearer <owner token>" }
```

A song with plays must answer `409` with the pt-BR `detail`. A fresh song must answer `204`.
