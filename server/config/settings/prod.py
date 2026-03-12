"""Production settings."""

from __future__ import annotations

import os
from config.settings.base import *  # noqa: F403

FORCE_SCRIPT_NAME = '/ipbcb'
USE_X_FORWARDED_HOST = True

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

def _require_csv_env(name: str) -> list[str]:
    value = (os.environ.get(name) or "").strip()
    if not value:
        raise RuntimeError(f"Missing required env var: {name}")
    return [part.strip() for part in value.split(",") if part.strip()]


SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]

ALLOWED_HOSTS = _require_csv_env("DJANGO_ALLOWED_HOSTS")
CSRF_TRUSTED_ORIGINS = _require_csv_env("DJANGO_CSRF_TRUSTED_ORIGINS")

CSRF_COOKIE_PATH = "/ipbcb/"
SESSION_COOKIE_PATH = "/ipbcb/"

CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SECURE = True


