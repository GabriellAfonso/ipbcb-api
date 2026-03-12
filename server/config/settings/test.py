"""Test settings — uses SQLite in-memory to avoid needing a Postgres instance."""

from .base import *  # noqa

DEBUG = True
ALLOWED_HOSTS = ["*"]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

# Disable secure cookies for tests
CSRF_COOKIE_SECURE = False
SESSION_COOKIE_SECURE = False
