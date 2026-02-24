"""Development settings."""

from .base import *  # noqa

DEBUG = True

ALLOWED_HOSTS = ["*"]

# Local dev: don't force secure cookies
CSRF_COOKIE_SECURE = False
SESSION_COOKIE_SECURE = False
