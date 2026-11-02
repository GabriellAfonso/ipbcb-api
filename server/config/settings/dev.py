"""Development settings."""

import os

from .base import *  # noqa

reject_dev_settings_in_production("config.settings.dev")  # noqa: F405

DEBUG = True

ALLOWED_HOSTS = ["*"]

# Local convenience only — production never reaches this branch, prod.py requires the
# env var. base.py deliberately has no fallback of its own.
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY") or "django-insecure-dev-only"  # nosec B105

# base.py froze SIGNING_KEY at import time, before the reassignment above.
SIMPLE_JWT = {**SIMPLE_JWT, "SIGNING_KEY": SECRET_KEY}  # noqa: F405

# Local dev: don't force secure cookies
CSRF_COOKIE_SECURE = False
SESSION_COOKIE_SECURE = False

# Local dev: messages with codes are printed, never sent.
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
