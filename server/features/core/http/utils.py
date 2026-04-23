import hashlib
import json
from typing import Any

from rest_framework.request import Request
from rest_framework.response import Response


def _make_etag_from_data(data: Any) -> str:
    payload = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )
    digest = hashlib.sha256(payload).hexdigest()
    return f'"{digest}"'


def _not_modified_or_response(
    request: Request,
    data: Any,
    status_code: int = 200,
    tag: str = "",
) -> Response:
    etag = _make_etag_from_data(data)
    inm = request.headers.get("If-None-Match")
    inm_clean = inm.strip() if inm else None

    method = getattr(request, "method", "")
    path = getattr(request, "path", "")
    tag_txt = f"[{tag}] " if tag else ""

    if inm_clean and inm_clean == etag:
        print(
            f"{tag_txt}HTTP 304 {method} {path} (If-None-Match={inm_clean}, ETag={etag}) -> sem body"
        )
        resp = Response(status=304)
        resp["ETag"] = etag
        return resp

    print(f"{tag_txt}HTTP 200 {method} {path} (If-None-Match={inm_clean}, ETag={etag}) -> COM body")
    resp = Response(data, status=status_code)
    resp["ETag"] = etag
    return resp
