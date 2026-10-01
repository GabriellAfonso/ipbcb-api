"""Base Django settings.

Keep environment-specific values in dev.py/prod.py.
"""

from __future__ import annotations
import dotenv

dotenv.load_dotenv()


import os  # noqa: E402
from datetime import timedelta  # noqa: E402
from pathlib import Path  # noqa: E402


BASE_DIR = Path(__file__).resolve().parent.parent.parent


def env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def reject_dev_settings_in_production(loaded_module: str) -> None:
    """Raise when DJANGO_ENV asks for production but a non-production module loaded.

    Production degrades silently under dev settings: it boots fine, just without HSTS,
    without secure cookies and with DEBUG on. Failing at import makes the mistake loud.

    >>> reject_dev_settings_in_production("config.settings.dev")
    """
    env = (os.environ.get("DJANGO_ENV") or "").strip().lower()
    if env not in {"prod", "production"}:
        return
    raise RuntimeError(
        f"DJANGO_ENV={env} but {loaded_module} was loaded. DJANGO_SETTINGS_MODULE is "
        f"overriding the DJANGO_ENV selection — expected config.settings.prod."
    )


# Core
# No fallback on purpose. A default key committed here becomes the JWT signing key the
# moment production loads the wrong settings module, turning a misconfiguration into a
# full authentication bypass. Each environment module supplies its own key.
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")

GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", default="")

# Firebase service account JSON, base64-encoded on one line (specs/017-sunday-setlist-push R-06).
# Empty disables push: saves and reminders still work, with a warning logged per send. Decoded
# only by core.push.factory, which never echoes the value in an error.
FCM_SERVICE_ACCOUNT_JSON_BASE64 = os.environ.get("FCM_SERVICE_ACCOUNT_JSON_BASE64", "")

DEBUG = env_bool("DJANGO_DEBUG", False)

AUTH_USER_MODEL = "accounts.User"

ALLOWED_HOSTS: list[str] = []


# Application definition
INSTALLED_APPS = [
    "django_prometheus",
    "rest_framework",
    "drf_spectacular",
    "rest_framework_simplejwt.token_blacklist",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "axes",
    # Shared layer. Holds only entities used by two or more features — the church
    # service catalogue is shared by schedule and songs, which may not import each other.
    "core",
    "features.accounts",
    "features.songs",
    "features.schedule",
    "features.members",
    "features.gallery",
    "features.bible",
]

MIDDLEWARE = [
    "django_prometheus.middleware.PrometheusBeforeMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "core.http.middleware.RequestLoggingMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # After AuthenticationMiddleware: it reads the lockout flag the axes backend sets on the
    # request. Before PrometheusAfterMiddleware: the 429s it produces must still be counted.
    "axes.middleware.AxesMiddleware",
    "django_prometheus.middleware.PrometheusAfterMiddleware",
]

ROOT_URLCONF = "config.urls"

# drf-spectacular falls back gracefully when it cannot infer a serializer from a plain
# APIView — informational, not a defect. Silenced so `check --deploy` in CI stays a
# signal: any warning it still reports is one worth reading.
SILENCED_SYSTEM_CHECKS = ["drf_spectacular.W002"]

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    }
]

WSGI_APPLICATION = "config.wsgi.application"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

DATABASES = {
    "default": {
        "ENGINE": "django_prometheus.db.backends.postgresql",
        "NAME": os.environ.get("POSTGRES_DB", ""),
        "USER": os.environ.get("POSTGRES_USER", ""),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD", ""),
        "HOST": os.environ.get("POSTGRES_HOST", "localhost"),
        "PORT": os.environ.get("POSTGRES_PORT", "5432"),
    }
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 6},
    },
]


# Auth / API
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=60),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=30),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "ALGORITHM": "HS256",
    # Frozen at import time. Every settings module that reassigns SECRET_KEY must also
    # reassign SIGNING_KEY, or tokens keep being signed with the value read right here.
    "SIGNING_KEY": SECRET_KEY,
    "AUTH_HEADER_TYPES": ("Bearer",),
    # Embeds a hash of the user's password in every token and checks it on each request,
    # so changing a password revokes every token that user holds — access tokens included,
    # on every device, immediately. Without it the only lever is deactivating the account,
    # and a leaked refresh token stays usable for its full 30 days.
    "CHECK_REVOKE_TOKEN": True,  # nosec B105 — a flag, not a credential
}

REST_FRAMEWORK = {
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ),
    "EXCEPTION_HANDLER": "core.http.exceptions.custom_exception_handler",
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "500/hour",
        "user": "1000/hour",
        "login": "10/min",
        # Sized for the whole congregation behind a single church-WiFi NAT address
        # (~200 devices syncing up to 3x/hour), not for one person. See
        # specs/006-hymnal-view-history/research.md R-02.
        "hymnal_ingest": "600/hour",
        # Its own scope so loading images never spends the API quota. Every image shown is a
        # request (revalidation under no-cache), 304 or not. specs/009-protected-media-access.
        "media": "3000/hour",
    },
    # The app runs behind nginx, which sets X-Forwarded-For. Without this, DRF trusts a
    # client-supplied XFF header as the throttle key and every rate limit can be bypassed
    # by rotating it.
    "NUM_PROXIES": 1,
}


# Brute-force lockout (django-axes)
# /ipbcb/admin/ is a plain Django view, so the DRF throttles above never reach it — without
# this block the superuser password is guessable at the rate four gunicorn workers can answer.
# Every value here overrides a library default that is wrong for this deployment; the reasoning
# is in specs/008-login-brute-force-lockout/plan.md.
AUTHENTICATION_BACKENDS = [
    # Must be first: it only monitors and blocks, it never authenticates. ModelBackend stays
    # the single place that checks the password and runs permission checks.
    "axes.backends.AxesStandaloneBackend",
    "django.contrib.auth.backends.ModelBackend",
]

# The Nth failure is itself refused with the lockout response, so this allows four
# informative 401s before the fifth attempt is turned away. Library default is 3.
AXES_FAILURE_LIMIT = 5
# Library default is None, which means locked out forever until an admin clears the row —
# a mistyped password would become a support call. It also bounds the counter: axes purges
# attempts older than this, so the limit above is really "five failures within 30 minutes".
AXES_COOLOFF_TIME = timedelta(minutes=30)
# Only reaches the Django admin. The reset hangs off Django's user_logged_in signal, which
# django.contrib.auth.login() sends and the JWT login does not — LoginAPI hands out tokens
# without ever creating a session. The API relies on the 30-minute window above instead.
AXES_RESET_ON_SUCCESS = True
# Combination, not two independent keys. Locking on ip_address alone (the library default)
# would lock the whole congregation out through the single church-WiFi NAT address; locking
# on username alone hands anyone a remote denial of service against the administrator.
AXES_LOCKOUT_PARAMETERS = [["username", "ip_address"]]
AXES_USERNAME_CALLABLE = "core.http.lockout.axes_lockout_username"
AXES_LOCKOUT_CALLABLE = "core.http.lockout.axes_lockout_response"
# Same reason as NUM_PROXIES above: behind nginx, REMOTE_ADDR (the library default) is the
# proxy for every client on earth, and a raw X-Forwarded-For lets a client pick its own key.
# REMOTE_ADDR stays as the fallback for dev and the test suite, which send no XFF header.
#
# "right-most" is what makes the header unspoofable: nginx appends the real peer address to
# whatever the client sent, so the rightmost entry is the only one a client cannot write.
# AXES_IPWARE_PROXY_COUNT is deliberately left unset — ipware reads it as "the header must
# hold exactly this many proxy hops" and returns None when it does not, which is the ordinary
# production case of a single-entry X-Forwarded-For. It is not DRF's NUM_PROXIES.
AXES_IPWARE_PROXY_ORDER = "right-most"
AXES_IPWARE_META_PRECEDENCE_ORDER = ("HTTP_X_FORWARDED_FOR", "REMOTE_ADDR")


# Internationalization
LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_TZ = True
USE_I18N = True


# Static/media
STATIC_URL = "/ipbcb/static/"
STATIC_ROOT = BASE_DIR / "static"

MEDIA_URL = "/ipbcb/media/"
MEDIA_ROOT = BASE_DIR / "media"
# nginx-internal location the media view hands files to via X-Accel-Redirect. Not a client
# URL: nginx marks it `internal`, so only a backend response can reach it.
# See specs/009-protected-media-access/contracts/media-endpoint.md.
PROTECTED_MEDIA_LOCATION = "/ipbcb/protected-media/"


# Logging
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "request_id": {
            "()": "core.logging.context.RequestIdFilter",
        },
    },
    "formatters": {
        "json": {
            "()": "pythonjsonlogger.json.JsonFormatter",
            "fmt": "%(timestamp)s %(level)s %(name)s %(message)s",
            "rename_fields": {"levelname": "level", "name": "logger"},
            "timestamp": True,
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
            "formatter": "json",
            "filters": ["request_id"],
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "django.request": {"level": "WARNING"},
        "django.server": {"level": "WARNING"},
        "django.db.backends": {"level": "WARNING"},
    },
}
