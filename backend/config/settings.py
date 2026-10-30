"""
Django settings for config project.
"""

from datetime import timedelta
from pathlib import Path

from decouple import AutoConfig

BASE_DIR = Path(__file__).resolve().parent.parent
config = AutoConfig(search_path=str(BASE_DIR))
PRIVATE_EVIDENCE_ROOT = config("PRIVATE_EVIDENCE_ROOT", default=str(BASE_DIR / "private_evidence"))
EVIDENCE_MAX_BYTES = 10 * 1024 * 1024

SECRET_KEY = config("DJANGO_SECRET_KEY")

DEBUG = config("DJANGO_DEBUG", default=False, cast=bool)

ALLOWED_HOSTS = config("DJANGO_ALLOWED_HOSTS", default="localhost,127.0.0.1").split(",")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third-party
    "rest_framework",
    "rest_framework_simplejwt",
    "corsheaders",
    "simple_history",
    # Local
    "accounts",
    "expenses",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "simple_history.middleware.HistoryRequestMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

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
    },
]

WSGI_APPLICATION = "config.wsgi.application"

from .database import database_settings

DATABASES = {"default": database_settings(config)}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
     "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ---------------------------------------------------------------------------
# Security hardening
# ---------------------------------------------------------------------------
SECURE_CONTENT_TYPE_NOSNIFF = config("SECURE_CONTENT_TYPE_NOSNIFF", default=True, cast=bool)
SECURE_BROWSER_XSS_FILTER = config("SECURE_BROWSER_XSS_FILTER", default=True, cast=bool)
X_FRAME_OPTIONS = "DENY"
SECURE_REFERRER_POLICY = "same-origin"

if not DEBUG:
    SECURE_SSL_REDIRECT = config("SECURE_SSL_REDIRECT", default=True, cast=bool)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = config("SECURE_HSTS_SECONDS", default=31536000, cast=int)

SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_USER_MODEL = "accounts.User"

# ---------------------------------------------------------------------------
# DRF
# ---------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_THROTTLE_CLASSES": (
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ),
    "DEFAULT_THROTTLE_RATES": {
        "anon": "60/minute",
        "user": "300/minute",
        "login": "5/minute",
        "password_change": "5/hour",
    },
    "EXCEPTION_HANDLER": "config.utils.exception_handler",
}

SIMPLE_JWT = {
    "CHECK_REVOKE_TOKEN": True,
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "UPDATE_LAST_LOGIN": True,
}

# ---------------------------------------------------------------------------
# Email — named mailers (Django MAILERS). All workflow notifications are sent
# through the "transactional" alias, so it can be pointed at SMTP independently
# of system mail just by changing EMAIL_BACKEND in .env.
# Console in dev (emails print in the runserver terminal); locmem under pytest
# so tests can assert on django.core.mail.outbox.
# ---------------------------------------------------------------------------
import sys  # noqa: E402

EMAIL_MAILER_BACKEND = config(
    "EMAIL_BACKEND",
    default="django.core.mail.backends.console.EmailBackend",
)
if "pytest" in sys.modules or "pytest" in sys.argv[0] or "test" in sys.argv[0]:
    EMAIL_MAILER_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

MAILERS = {
    "default": {"BACKEND": EMAIL_MAILER_BACKEND},
    "transactional": {"BACKEND": EMAIL_MAILER_BACKEND},
}

# Named mailers do not inherit the old EMAIL_HOST settings automatically.
if EMAIL_MAILER_BACKEND == "django.core.mail.backends.smtp.EmailBackend":
    smtp_options = {
        "host": config("EMAIL_HOST", default=""),
        "port": config("EMAIL_PORT", default=587, cast=int),
        "username": config("EMAIL_HOST_USER", default=""),
        "password": config("EMAIL_HOST_PASSWORD", default=""),
        "use_tls": config("EMAIL_USE_TLS", default=True, cast=bool),
        "use_ssl": config("EMAIL_USE_SSL", default=False, cast=bool),
        "timeout": config("EMAIL_TIMEOUT", default=15, cast=int),
    }
    MAILERS["default"]["OPTIONS"] = smtp_options.copy()
    MAILERS["transactional"]["OPTIONS"] = smtp_options.copy()

FRONTEND_URL = config("FRONTEND_URL", default="http://127.0.0.1:5174")
EMAIL_TEST_MODE = config("EMAIL_TEST_MODE", default=False, cast=bool)
# Personal mailbox routes are retired. Retain their tables for migration/data
# compatibility, but do not expose them through the application.
EMAIL_PERSONAL_CONNECTIONS_ENABLED = False
_mail_key_file = BASE_DIR / ".email-token.key"
EMAIL_TOKEN_KEY = config("EMAIL_TOKEN_KEY", default=_mail_key_file.read_text(encoding="ascii").strip() if _mail_key_file.exists() else "")
EMAIL_OAUTH_REDIRECT_URI = config("EMAIL_OAUTH_REDIRECT_URI", default=FRONTEND_URL.rstrip('/') + "/settings/email-callback")
GMAIL_CLIENT_ID = config("GMAIL_CLIENT_ID", default="")
GMAIL_CLIENT_SECRET = config("GMAIL_CLIENT_SECRET", default="")
ZOHO_CLIENT_ID = config("ZOHO_CLIENT_ID", default="")
ZOHO_CLIENT_SECRET = config("ZOHO_CLIENT_SECRET", default="")
# Fixed provider hosts: user input and OAuth callbacks cannot select a server.
ZOHO_REGION = config("ZOHO_REGION", default="com")

DEFAULT_FROM_EMAIL = config("DEFAULT_FROM_EMAIL", default="homebase-expenses@localhost")
SERVER_EMAIL = DEFAULT_FROM_EMAIL

ADMINS = []

# ---------------------------------------------------------------------------
# CORS — allow the Vite dev server
# ---------------------------------------------------------------------------
CORS_ALLOWED_ORIGINS = config(
    "CORS_ALLOWED_ORIGINS",
    default="http://localhost:5174,http://127.0.0.1:5174",
).split(",")
