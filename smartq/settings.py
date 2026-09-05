"""
Django settings for Smart Q.

Day 38 keeps SQLite3 as the project database while making production-facing
security configuration explicit, environment-driven and fail-fast.
"""

import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured


BASE_DIR = Path(__file__).resolve().parent.parent


def env_bool(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_list(name, default=None):
    value = os.getenv(name)
    if value is None:
        return list(default or [])
    return [item.strip() for item in value.split(",") if item.strip()]


SMARTQ_ENV = os.getenv("SMARTQ_ENV", "development").strip().lower()
IS_PRODUCTION = SMARTQ_ENV == "production"

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY")
if IS_PRODUCTION and not SECRET_KEY:
    raise ImproperlyConfigured("DJANGO_SECRET_KEY is required in production.")
if not SECRET_KEY:
    SECRET_KEY = "django-insecure-smartq-development-only-key"

DEBUG = env_bool("DJANGO_DEBUG", default=not IS_PRODUCTION)
if IS_PRODUCTION and DEBUG:
    raise ImproperlyConfigured("DJANGO_DEBUG must be false in production.")

ALLOWED_HOSTS = env_list(
    "ALLOWED_HOSTS",
    default=["127.0.0.1", "localhost"] if not IS_PRODUCTION else [],
)
if IS_PRODUCTION and not ALLOWED_HOSTS:
    raise ImproperlyConfigured("ALLOWED_HOSTS is required in production.")

# GitHub Codespaces exposes Django through an HTTPS forwarded hostname rather
# than localhost. In development only, trust the current Codespace host
# automatically so a fresh Codespace can log in without manual CSRF exports.
CODESPACE_NAME = os.getenv("CODESPACE_NAME", "").strip()
CODESPACES_DOMAIN = os.getenv(
    "GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN",
    "app.github.dev",
).strip()
SMARTQ_DEV_PORT = os.getenv("SMARTQ_DEV_PORT", "8000").strip()
CODESPACE_HOST = ""
if not IS_PRODUCTION and CODESPACE_NAME and CODESPACES_DOMAIN:
    CODESPACE_HOST = f"{CODESPACE_NAME}-{SMARTQ_DEV_PORT}.{CODESPACES_DOMAIN}"
    if CODESPACE_HOST not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(CODESPACE_HOST)


INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "queues",
    "branches",
    "services",
    "bookings",
    "accounts",
    "counters",
    "notifications",
    "rescheduling",
    "dashboard",
    "corsheaders",
    "rest_framework",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "smartq.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "smartq.wsgi.application"


# Database
# Smart Q uses SQLite3 for this project. The path can be overridden for a
# deployment that mounts persistent storage; otherwise db.sqlite3 is used.
SQLITE_PATH = os.getenv("SMARTQ_SQLITE_PATH")
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": Path(SQLITE_PATH) if SQLITE_PATH else BASE_DIR / "db.sqlite3",
    }
}


AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


REST_FRAMEWORK = {
    "DEFAULT_THROTTLE_RATES": {
        "login": "10/min",
        "account_security": "10/min",
    }
}


# Browser-origin policy.
# Session authentication means cross-origin frontend requests require both CORS
# permission and Django CSRF trust. We never enable allow-all origins.
CORS_ALLOWED_ORIGINS = env_list("CORS_ALLOWED_ORIGINS")
CORS_ALLOW_CREDENTIALS = env_bool("CORS_ALLOW_CREDENTIALS", default=True)
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS")

# Local development may be opened through either HTTP or an HTTPS localhost
# proxy/preview. Trust only these explicit loopback origins and only outside
# production. This keeps local/Codespaces smoke tests usable without weakening
# the production origin policy.
if not IS_PRODUCTION:
    for local_origin in [
        f"http://localhost:{SMARTQ_DEV_PORT}",
        f"https://localhost:{SMARTQ_DEV_PORT}",
        f"http://127.0.0.1:{SMARTQ_DEV_PORT}",
        f"https://127.0.0.1:{SMARTQ_DEV_PORT}",
    ]:
        if local_origin not in CSRF_TRUSTED_ORIGINS:
            CSRF_TRUSTED_ORIGINS.append(local_origin)

if CODESPACE_HOST:
    codespace_origin = f"https://{CODESPACE_HOST}"
    if codespace_origin not in CSRF_TRUSTED_ORIGINS:
        CSRF_TRUSTED_ORIGINS.append(codespace_origin)

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = IS_PRODUCTION
CSRF_COOKIE_SECURE = IS_PRODUCTION
SESSION_COOKIE_SAMESITE = os.getenv("SESSION_COOKIE_SAMESITE", "Lax")
CSRF_COOKIE_SAMESITE = os.getenv("CSRF_COOKIE_SAMESITE", "Lax")


# HTTPS/security settings.
SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", default=IS_PRODUCTION)
SECURE_HSTS_SECONDS = int(
    os.getenv("SECURE_HSTS_SECONDS", "3600" if IS_PRODUCTION else "0")
)
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool(
    "SECURE_HSTS_INCLUDE_SUBDOMAINS",
    default=False,
)
SECURE_HSTS_PRELOAD = env_bool("SECURE_HSTS_PRELOAD", default=False)
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

# Most production deployments place Django behind a trusted HTTPS reverse proxy.
# Enable this only when that proxy strips/replaces X-Forwarded-Proto itself.
if env_bool("USE_X_FORWARDED_PROTO", default=IS_PRODUCTION):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")


LANGUAGE_CODE = "en-us"
# Smart Q's current operating deployment is South African. Appointment clocks,
# check-in windows and branch operating hours must therefore use local SAST by
# default rather than UTC. Future multi-region deployments can override this
# without changing code until per-branch time zones are introduced.
TIME_ZONE = os.getenv("SMARTQ_TIME_ZONE", "Africa/Johannesburg")
USE_I18N = True
USE_TZ = True


STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]


# Production-friendly console logging. Infrastructure can collect stdout/stderr
# without Smart Q writing application log files inside ephemeral containers.
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "{asctime} {levelname} {name} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "standard",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": LOG_LEVEL,
    },
    "loggers": {
        "django.security": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
    },
}
