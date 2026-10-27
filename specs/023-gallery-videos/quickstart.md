# Quickstart: Gallery Videos

Commands from `server/` with `..\.venv_windows\Scripts\python.exe`.

## 1. Tests

```powershell
..\.venv_windows\Scripts\python.exe -m pytest features/gallery features/media core -q
..\.venv_windows\Scripts\python.exe -m pytest -q          # full suite, once at the end
```

Expected: green, including the new video validation, upload, resource, backfill and media
content-type tests.

## 2. Migration

```powershell
..\.venv_windows\Scripts\python.exe manage.py makemigrations --check --dry-run   # nothing left
..\.venv_windows\Scripts\python.exe manage.py migrate gallery 0007
..\.venv_windows\Scripts\python.exe manage.py migrate gallery 0006               # rollback runs
```

## 3. Manual upload (dev server)

```powershell
curl -X POST http://localhost:8000/ipbcb/api/photos/ -H "Authorization: Bearer $TOKEN" `
  -F album_id=1 -F video=@clip.mp4 -F poster=@poster.jpg -F duration_ms=45000 `
  -F client_upload_id=test-video-1
```

Expected `201` with `media_type` `video`. Resend: `201`, same id. Send `clip.mkv`: `400` with
"Formato de vídeo não suportado. Use MP4 ou MOV.".

## 4. Backfill (production, once after deploy)

```sh
docker exec ipbcb-server-prod python manage.py fill_gallery_file_sizes
docker exec ipbcb-server-prod python manage.py fill_gallery_file_sizes   # filled 0
```

## 5. Range end to end (production, once a video exists)

```sh
curl -s -o /dev/null -D - -H "Authorization: Bearer $TOKEN" -H "Range: bytes=1000-" \
  https://gabrielafonso.com.br/ipbcb/media/gallery/<album>/<uuid>.mp4
```

Expected `HTTP/1.1 206 Partial Content`, `Content-Range: bytes 1000-…/<size>`,
`Content-Type: video/mp4`, `Cache-Control: private, no-cache`.
