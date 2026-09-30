"""Test settings — uses SQLite in-memory to avoid needing a Postgres instance."""

from .base import *  # noqa

DEBUG = True
ALLOWED_HOSTS = ["*"]

# base.py has no fallback key, so the suite supplies its own.
# At least 32 bytes: PyJWT warns below that for HS256 (RFC 7518 §3.2).
SECRET_KEY = "insecure-test-only-key-with-enough-bytes-for-hs256"  # nosec B105
SIMPLE_JWT = {**SIMPLE_JWT, "SIGNING_KEY": SECRET_KEY}  # noqa: F405

# PBKDF2 is slow by design and the suite hashes a password in almost every test (make_user,
# logins): the default hasher took the full run from ~1 min to ~15 min. Production keeps PBKDF2.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

# Disable secure cookies for tests
CSRF_COOKIE_SECURE = False
SESSION_COOKIE_SECURE = False

# Disable throttling in tests
REST_FRAMEWORK = {
    **REST_FRAMEWORK,  # noqa: F405
    "DEFAULT_THROTTLE_CLASSES": [],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "99999/min",
        "user": "99999/min",
        "login": "99999/min",
        # Views that declare throttle_classes explicitly (hymnal ingest) keep throttling
        # even when DEFAULT_THROTTLE_CLASSES is empty, so the scope must exist here.
        "hymnal_ingest": "99999/min",
        # Same for the media view, which declares ScopedRateThrottle itself.
        "media": "99999/min",
    },
}

# Off by default: the suite logs in with wrong passwords on purpose, and one test's failures
# must never lock another test out (CLAUDE.md §10, F.I.R.S.T — independent). The tests that
# exercise the lockout switch it on with @override_settings(AXES_ENABLED=True); the library
# reads this flag at call time, so the override takes effect.
AXES_ENABLED = False
