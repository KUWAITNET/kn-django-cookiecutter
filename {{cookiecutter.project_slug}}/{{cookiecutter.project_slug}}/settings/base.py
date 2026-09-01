"""Base settings for {{ cookiecutter.project_name }}.

Configuration is environment-driven (12-factor) via django-environ. Secrets and
per-environment values come from the process environment or a local ``.env`` file
(see ``.env.example``). The ``dev``, ``production`` and ``test`` modules import from
here and override.

Production deliberately provides NO fallback for secrets, so a misconfigured deploy
fails loudly at boot rather than silently running with a development key.
"""

import os
{% if cookiecutter.api != "none" %}from datetime import timedelta
{% endif %}
import environ
from csp.constants import NONCE

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE_DIR = os.path.dirname(PROJECT_DIR)

env = environ.Env(
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, ["localhost", "127.0.0.1"]),
)

_env_file = os.path.join(BASE_DIR, ".env")
if os.path.exists(_env_file):
    environ.Env.read_env(_env_file)


# Security -------------------------------------------------------------------

SECRET_KEY = env("SECRET_KEY", default="django-insecure-change-me-for-dev-only")
DEBUG = env("DEBUG")
ALLOWED_HOSTS = env("ALLOWED_HOSTS")


# Application definition ------------------------------------------------------

INSTALLED_APPS = [
{%- if cookiecutter.stack == "wagtail" %}
    # Wagtail
    "wagtail.contrib.forms",
    "wagtail.contrib.redirects",
    "wagtail.contrib.settings",
    "wagtail.contrib.table_block",
    "wagtail.contrib.routable_page",
{%- if cookiecutter.api == "headless" %}
    "wagtail.api.v2",
{%- endif %}
    "wagtail.embeds",
    "wagtail.sites",
    "wagtail.users",
    "wagtail.snippets",
    "wagtail.documents",
    "wagtail.images",
    "wagtail.search",
    "wagtail.admin",
    "wagtail",
    "modelcluster",
    "taggit",
{%- endif %}
    # Admin skin. "unfold" must precede django.contrib.admin.
    "unfold",
    "unfold.contrib.filters",
    "unfold.contrib.forms",
    # Third party
{%- if cookiecutter.countries_app == "yes" %}
    "cities_light",
{%- endif %}
{%- if cookiecutter.countries_app == "yes" or cookiecutter.forms_suite == "yes" %}
    "phonenumber_field",
{%- endif %}
{%- if cookiecutter.use_2fa == "yes" %}
    "django_otp",
    "django_otp.plugins.otp_totp",
    "django_otp.plugins.otp_static",
{%- if cookiecutter.stack == "wagtail" %}
    "wagtail_2fa",
{%- endif %}
{%- endif %}
{%- if cookiecutter.rate_limiting == "yes" %}
    "axes",
{%- endif %}
    "post_office",
{%- if cookiecutter.api != "none" %}
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "drf_spectacular",
    "corsheaders",
    "django_filters",
{%- endif %}
{%- if cookiecutter.languages == "en_ar" %}
{%- if cookiecutter.stack == "wagtail" %}
    # Registers Page and patches the admin. MUST precede any project app that
    # registers a Page subclass in its translation.py.
    "wagtail_modeltranslation",
    "wagtail_modeltranslation.makemigrations",
    "wagtail_modeltranslation.migrate",
{%- else %}
    # Must precede django.contrib.admin.
    "modeltranslation",
{%- endif %}
{%- endif %}
    # Project
    "apps.core",
{%- if cookiecutter.countries_app == "yes" %}
    "apps.cities",
{%- endif %}
{%- if cookiecutter.notifications_app == "yes" %}
    "apps.notifications",
{%- endif %}
{%- if cookiecutter.stack == "wagtail" %}
    "apps.navigation",
    "apps.home",
{%- if cookiecutter.frontend != "api_only" %}
    "apps.search",
{%- endif %}
{%- endif %}
{%- if cookiecutter.forms_suite == "yes" %}
    "apps.contact",
{%- endif %}
{%- if cookiecutter.newsletter == "yes" %}
    "apps.newsletter",
{%- endif %}
{%- if cookiecutter.api != "none" %}
    "apps.api",
{%- endif %}
    # Django. The admin app is loaded through our own AppConfig so that the admin
    # site class (Unfold{% if cookiecutter.use_2fa == "yes" %}, with two-factor enforcement{% endif %}) is applied. It lives in its own
    # module because Django refuses to auto-discover an app config when a single
    # apps.py defines more than one AppConfig subclass.
    "apps.core.admin_config.KuwaitnetAdminConfig",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.sitemaps",
    # Required from Django 6.1: the postgres.E005 system check rejects
    # SearchVectorField and GinIndex unless this app is installed, and the search
    # index uses both. Harmless on 5.2, and this project is PostgreSQL-only anyway.
    "django.contrib.postgres",
    "django.contrib.staticfiles",
]

MIDDLEWARE = [
{%- if cookiecutter.api != "none" %}
    # CORS must come before CommonMiddleware so preflight responses carry the headers.
    "corsheaders.middleware.CorsMiddleware",
{%- endif %}
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
{%- if cookiecutter.languages == "en_ar" %}
    "django.middleware.locale.LocaleMiddleware",
{%- endif %}
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
{%- if cookiecutter.use_2fa == "yes" %}
    # django-otp must follow AuthenticationMiddleware.
    "django_otp.middleware.OTPMiddleware",
{%- if cookiecutter.stack == "wagtail" %}
    "wagtail_2fa.middleware.VerifyUserMiddleware",
{%- endif %}
{%- endif %}
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # Security response headers.
    "csp.middleware.CSPMiddleware",
    "django_permissions_policy.PermissionsPolicyMiddleware",
{%- if cookiecutter.rate_limiting == "yes" %}
    # AxesMiddleware must come last: it needs the authenticated user.
    "axes.middleware.AxesMiddleware",
{%- endif %}
{%- if cookiecutter.stack == "wagtail" %}
    "wagtail.contrib.redirects.middleware.RedirectMiddleware",
{%- endif %}
]

ROOT_URLCONF = "{{ cookiecutter.project_slug }}.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [os.path.join(PROJECT_DIR, "templates")],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "django.template.context_processors.i18n",
{%- if cookiecutter.stack == "wagtail" %}
                "wagtail.contrib.settings.context_processors.settings",
{%- endif %}
                "apps.core.context_processors.site_context",
            ],
        },
    },
]

WSGI_APPLICATION = "{{ cookiecutter.project_slug }}.wsgi.application"


# Database -------------------------------------------------------------------

DATABASES = {
    "default": env.db(
        "DATABASE_URL",
        default="postgres://postgres:postgres@localhost:5432/{{ cookiecutter.project_slug }}",
    ),
}
DATABASES["default"].setdefault("CONN_MAX_AGE", 60)


# Cache ----------------------------------------------------------------------
{% if cookiecutter.cache == "redis" %}
# Rate limiting and DRF throttling keep their counters here. With a per-process
# cache each gunicorn worker would keep its own counter, so production must use a
# shared backend (see production.py, which enforces this).
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": env("REDIS_URL", default="redis://127.0.0.1:6379/1"),
    }
}
{%- else %}
# Local-memory cache. NOTE: this is per-process. With N gunicorn workers a
# "10/minute" rate limit becomes 10*N per minute, so production must be switched to
# Redis before go-live (production.py warns when it is not).
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "{{ cookiecutter.project_slug }}",
    }
}
{%- endif %}


# Authentication -------------------------------------------------------------

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 12},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Argon2 first; PBKDF2 retained so existing hashes still verify and are upgraded
# on next login.
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
]
{% if cookiecutter.rate_limiting == "yes" %}
AUTHENTICATION_BACKENDS = [
    # AxesStandaloneBackend must come first so lockouts are enforced before any
    # credential check.
    "axes.backends.AxesStandaloneBackend",
    "django.contrib.auth.backends.ModelBackend",
]

# Brute-force lockout (django-axes). A lockout with an auditable record is a
# different control from a rate cap - see the security baseline.
AXES_FAILURE_LIMIT = env.int("AXES_FAILURE_LIMIT", default=5)
AXES_COOLOFF_TIME = env.float("AXES_COOLOFF_HOURS", default=0.5)
AXES_LOCKOUT_PARAMETERS = [["username", "ip_address"]]
AXES_RESET_ON_SUCCESS = True
AXES_ENABLE_ADMIN = True
AXES_VERBOSE = True
# IMPORTANT: behind a proxy, set AXES_IPWARE_PROXY_COUNT so the real client IP is
# used. With the wrong value every request appears to come from the load balancer
# and one attacker locks out every user.
AXES_IPWARE_PROXY_COUNT = env.int("AXES_IPWARE_PROXY_COUNT", default=0) or None
{%- else %}
AUTHENTICATION_BACKENDS = ["django.contrib.auth.backends.ModelBackend"]
{%- endif %}

LOGIN_URL = "/{{ cookiecutter.admin_url_prefix }}/login/"
{% if cookiecutter.use_2fa == "yes" %}
# Two-factor authentication is required for every administrative account.
{%- if cookiecutter.stack == "wagtail" %}
WAGTAIL_2FA_REQUIRED = env.bool("WAGTAIL_2FA_REQUIRED", default=True)
{%- else %}
OTP_ADMIN_REQUIRED = env.bool("OTP_ADMIN_REQUIRED", default=True)
{%- endif %}
OTP_TOTP_ISSUER = "{{ cookiecutter.project_name }}"
{%- endif %}


# Internationalisation --------------------------------------------------------
{% if cookiecutter.languages == "en_ar" %}
LANGUAGE_CODE = "en"
LANGUAGES = [
    ("en", "English"),
    ("ar", "العربية"),
]
LOCALE_PATHS = [os.path.join(PROJECT_DIR, "locale")]

# Per-field translation: one content tree, translated columns per language.
MODELTRANSLATION_DEFAULT_LANGUAGE = "en"
MODELTRANSLATION_LANGUAGES = ("en", "ar")
MODELTRANSLATION_FALLBACK_LANGUAGES = ("en", "ar")
{%- else %}
LANGUAGE_CODE = "en"
LANGUAGES = [("en", "English")]
LOCALE_PATHS = [os.path.join(PROJECT_DIR, "locale")]
{%- endif %}

TIME_ZONE = "{{ cookiecutter.timezone }}"
USE_I18N = True
USE_TZ = True


# Static and media -------------------------------------------------------------

STATICFILES_FINDERS = [
    "django.contrib.staticfiles.finders.FileSystemFinder",
    "django.contrib.staticfiles.finders.AppDirectoriesFinder",
]
{% if cookiecutter.frontend != "api_only" %}
STATICFILES_DIRS = [os.path.join(PROJECT_DIR, "static")]
{%- else %}
STATICFILES_DIRS = []
{%- endif %}
STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")
STATIC_URL = "/static/"

MEDIA_ROOT = env("MEDIA_ROOT", default=os.path.join(BASE_DIR, "media"))
MEDIA_URL = "/media/"

# Uploads containing personal data are served through a permission-checked view,
# never from MEDIA_URL. See apps.core.storage and the security baseline.
PRIVATE_MEDIA_ROOT = env("PRIVATE_MEDIA_ROOT", default=os.path.join(BASE_DIR, "private-media"))

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        # Hashed filenames: cache-busting without hand-stamped ?v= query strings.
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Complex page models can exceed Django's default form field limit.
DATA_UPLOAD_MAX_NUMBER_FIELDS = 10_000


# Uploads ---------------------------------------------------------------------

# Request body cap (10 MB). Per-field limits are enforced by the validators in
# apps.core.validators, which also check the file's real content type.
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024

# Per-field defaults consumed by apps.core.validators.
UPLOAD_MAX_SIZE_MB = env.int("UPLOAD_MAX_SIZE_MB", default=10)
UPLOAD_IMAGE_MAX_PIXELS = env.int("UPLOAD_IMAGE_MAX_PIXELS", default=50_000_000)


# E-mail -----------------------------------------------------------------------
#
# django-post-office sits in front of whichever real backend is selected below: it
# logs every send (visible in the admin) and supplies the admin-editable template
# model. Django's own EMAIL_BACKEND is always post_office's, so every send in the
# codebase goes through it unchanged.

if env("EMAIL_URL", default=""):
    _email_url_config = env.email_url("EMAIL_URL")
    vars().update(_email_url_config)
    _real_email_backend = _email_url_config["EMAIL_BACKEND"]
elif env("EMAIL_HOST", default=""):
    _real_email_backend = env(
        "EMAIL_BACKEND", default="django.core.mail.backends.smtp.EmailBackend"
    )
    EMAIL_HOST = env("EMAIL_HOST")
    EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
    EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
    EMAIL_PORT = env.int("EMAIL_PORT", default=587)
    EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
    EMAIL_USE_SSL = env.bool("EMAIL_USE_SSL", default=False)
else:
    _real_email_backend = "django.core.mail.backends.console.EmailBackend"

EMAIL_BACKEND = "post_office.EmailBackend"
POST_OFFICE = {
    "BACKENDS": {"default": _real_email_backend},
    # Deliver synchronously: no send_queued_mail cron dependency.
    "DEFAULT_PRIORITY": "now",
    "LOG_LEVEL": 2,
}

DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="{{ cookiecutter.author_email }}")
SERVER_EMAIL = env("SERVER_EMAIL", default=DEFAULT_FROM_EMAIL)

# Fallback recipient(s) for notification e-mails (comma separated).
DEFAULT_ADMIN_EMAIL = env("DEFAULT_ADMIN_EMAIL", default="{{ cookiecutter.author_email }}")


# Site identity ----------------------------------------------------------------

SITE_NAME = env("SITE_NAME", default="{{ cookiecutter.project_name }}")
CLIENT_NAME = "{{ cookiecutter.client_name }}"
BASE_URL = env("BASE_URL", default="http://localhost:8000")

# Staging/UAT must never be indexed. Basic auth alone has repeatedly leaked through
# shared links and screenshots, and an indexed UAT site competes with production in
# search results. Production sets this to False.
ROBOTS_DISALLOW_ALL = env.bool("ROBOTS_DISALLOW_ALL", default=True)
{%- if cookiecutter.stack == "wagtail" %}
WAGTAIL_SITE_NAME = SITE_NAME
WAGTAILADMIN_BASE_URL = BASE_URL
WAGTAIL_ENABLE_UPDATE_CHECK = False
WAGTAIL_ENABLE_WHATS_NEW_BANNER = False
WAGTAIL_ALLOW_UNICODE_SLUGS = False

WAGTAILSEARCH_BACKENDS = {"default": {"BACKEND": "wagtail.search.backends.database"}}

WAGTAILIMAGES_IMAGE_MODEL = "core.CustomImage"
WAGTAILIMAGES_RENDITION_MODEL = "core.CustomRendition"
# SVG is executable markup, not an image. It is deliberately excluded.
WAGTAILIMAGES_EXTENSIONS = ["avif", "gif", "jpg", "jpeg", "png", "webp"]
WAGTAILIMAGES_MAX_UPLOAD_SIZE = UPLOAD_MAX_SIZE_MB * 1024 * 1024
WAGTAILDOCS_EXTENSIONS = ["csv", "docx", "odt", "pdf", "pptx", "rtf", "txt", "xlsx", "zip"]
WAGTAILDOCS_SERVE_METHOD = "serve_view"
{%- endif %}


# Security ---------------------------------------------------------------------
# TLS-dependent toggles live in production.py so local development over HTTP keeps
# working and nobody disables them globally to fix a dev problem.

X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = env.int("SESSION_COOKIE_AGE", default=60 * 60 * 12)
CSRF_COOKIE_SAMESITE = "Lax"

# Content-Security-Policy (django-csp 4.x).
#
# Inline scripts use the per-request nonce ({% raw %}{{ request.csp_nonce }}{% endraw %}); there is no
# 'unsafe-inline' and no 'unsafe-eval' in script-src. If a vendored theme library
# needs eval, that is a finding to fix or a documented, time-boxed exception - not
# a permanent setting.
CONTENT_SECURITY_POLICY = {
    "DIRECTIVES": {
        "default-src": ["'self'"],
        "script-src": [
            "'self'",
            # django-csp 4.x replaces this sentinel with the per-request nonce.
            NONCE,
{%- if cookiecutter.analytics == "ga4_gtm" %}
            "https://www.googletagmanager.com",
            "https://www.google-analytics.com",
{%- endif %}
{%- if cookiecutter.spam_protection == "turnstile_honeypot" %}
            "https://challenges.cloudflare.com",
{%- endif %}
        ],
        # Styles are self-hosted. Inline style attributes still require this;
        # remove it once the theme has none.
        "style-src": ["'self'", "'unsafe-inline'"],
        "font-src": ["'self'", "data:"],
        "img-src": [
            "'self'",
            "data:",
{%- if cookiecutter.analytics == "ga4_gtm" %}
            "https://www.googletagmanager.com",
            "https://www.google-analytics.com",
{%- endif %}
        ],
        "connect-src": [
            "'self'",
{%- if cookiecutter.analytics == "ga4_gtm" %}
            "https://www.google-analytics.com",
            "https://analytics.google.com",
{%- endif %}
        ],
        "frame-src": [
            "'self'",
{%- if cookiecutter.spam_protection == "turnstile_honeypot" %}
            "https://challenges.cloudflare.com",
{%- endif %}
{%- if cookiecutter.analytics == "ga4_gtm" %}
            # The GTM <noscript> fallback is an iframe. Allowing it here is far
            # cheaper than loosening script-src.
            "https://www.googletagmanager.com",
{%- endif %}
        ],
        "frame-ancestors": ["'self'"],
        "base-uri": ["'self'"],
        "form-action": ["'self'"],
        "object-src": ["'none'"],
    },
}

# Deny every browser feature the site does not use. Enable explicitly, with a reason.
PERMISSIONS_POLICY = {
    "accelerometer": [],
    "camera": [],
    "display-capture": [],
    "geolocation": [],
    "gyroscope": [],
    "magnetometer": [],
    "microphone": [],
    "payment": [],
    "usb": [],
}
{% if cookiecutter.spam_protection == "turnstile_honeypot" %}
# Cloudflare Turnstile. With no keys configured the protection degrades to
# honeypot-only so development, CI and UAT are never blocked - but production
# without a key is a go-live finding (production.py warns).
TURNSTILE_SITE_KEY = env("TURNSTILE_SITE_KEY", default="")
TURNSTILE_SECRET_KEY = env("TURNSTILE_SECRET_KEY", default="")
TURNSTILE_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
TURNSTILE_TIMEOUT = 5
{%- endif %}
{%- if cookiecutter.spam_protection != "none" %}
SPAM_PROTECTION = "{{ cookiecutter.spam_protection }}"
{%- else %}
# Generated with spam protection disabled. This is a documented exception under
# the security baseline; record it in docs/14-decisions.md.
SPAM_PROTECTION = "none"
{%- endif %}
{% if cookiecutter.rate_limiting == "yes" and cookiecutter.frontend != "api_only" %}
# django-ratelimit budgets for non-DRF public POST endpoints. Endpoints that send
# e-mail or write files get the tightest budgets: each request costs an external
# resource.
RATELIMIT_FORM_SUBMIT = env("RATELIMIT_FORM_SUBMIT", default="5/h")
RATELIMIT_NEWSLETTER = env("RATELIMIT_NEWSLETTER", default="3/h")
RATELIMIT_SEARCH = env("RATELIMIT_SEARCH", default="30/m")
{%- endif %}


# Analytics --------------------------------------------------------------------
{% if cookiecutter.analytics == "ga4_gtm" %}
# Empty in every environment but production, so staging traffic never pollutes the
# client's analytics property.
GA4_MEASUREMENT_ID = env("GA4_MEASUREMENT_ID", default="")
GTM_CONTAINER_ID = env("GTM_CONTAINER_ID", default="")
{%- else %}
GA4_MEASUREMENT_ID = ""
GTM_CONTAINER_ID = ""
{%- endif %}
{% if cookiecutter.api != "none" %}

# API ---------------------------------------------------------------------------
# Implements api-standard.md. Deny by default; public endpoints opt in explicitly.

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_PAGINATION_CLASS": "apps.api.pagination.DefaultPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.OrderingFilter",
        "rest_framework.filters.SearchFilter",
    ],
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": env("THROTTLE_ANON", default="60/min"),
        "user": env("THROTTLE_USER", default="600/hour"),
        "auth": env("THROTTLE_AUTH", default="10/min"),
        "write": env("THROTTLE_WRITE", default="60/hour"),
    },
    # Single error envelope: RFC 9457 application/problem+json.
    "EXCEPTION_HANDLER": "apps.api.exceptions.problem_detail_handler",
    "DEFAULT_VERSIONING_CLASS": "rest_framework.versioning.URLPathVersioning",
    "DEFAULT_VERSION": "v1",
    "ALLOWED_VERSIONS": ["v1"],
    "TEST_REQUEST_DEFAULT_FORMAT": "json",
    # JSON only. DRF's default list includes the browsable API, which would
    # otherwise be live in production.
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
        "rest_framework.parsers.MultiPartParser",
    ],
}

if DEBUG:
    REST_FRAMEWORK["DEFAULT_RENDERER_CLASSES"] = [
        *REST_FRAMEWORK["DEFAULT_RENDERER_CLASSES"],
        "rest_framework.renderers.BrowsableAPIRenderer",
    ]

# Base URI for the "type" member of RFC 9457 problem documents.
API_PROBLEM_BASE_URL = env("API_PROBLEM_BASE_URL", default=f"{BASE_URL}/api/problems")

# Outbound integration (apps/api/services.py). Absent settings make the client
# refuse to construct with a clear error rather than failing at call time.
INTEGRATION_BASE_URL = env("INTEGRATION_BASE_URL", default="")
INTEGRATION_USERNAME = env("INTEGRATION_USERNAME", default="")
INTEGRATION_PASSWORD = env("INTEGRATION_PASSWORD", default="")
INTEGRATION_TIMEOUT_CONNECT = env.float("INTEGRATION_TIMEOUT_CONNECT", default=5.0)
INTEGRATION_TIMEOUT_READ = env.float("INTEGRATION_TIMEOUT_READ", default=20.0)
INTEGRATION_FORCE_TLS12 = env.bool("INTEGRATION_FORCE_TLS12", default=False)
{%- if cookiecutter.api == "headless" %}

# Page/image/document API. Cap the page size: an uncapped list endpoint is the
# "unrestricted resource consumption" item of the OWASP API Top 10.
WAGTAILAPI_LIMIT_MAX = 100
WAGTAILAPI_SEARCH_ENABLED = True
{%- endif %}

SPECTACULAR_SETTINGS = {
    "TITLE": "{{ cookiecutter.project_name }} API",
    "DESCRIPTION": "{{ cookiecutter.description }}",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "SCHEMA_PATH_PREFIX": "/api/v[0-9]",
    "COMPONENT_SPLIT_REQUEST": True,
    "SORT_OPERATIONS": True,
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=env.int("JWT_ACCESS_MINUTES", default=15)),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=env.int("JWT_REFRESH_DAYS", default=7)),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": env("JWT_SIGNING_KEY", default=SECRET_KEY),
}

# Explicit origins only. Never a wildcard with credentials.
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=[])
CORS_ALLOW_CREDENTIALS = env.bool("CORS_ALLOW_CREDENTIALS", default=False)
CORS_URLS_REGEX = r"^/api/.*$"
CORS_PREFLIGHT_MAX_AGE = 3600

# The schema UI is served on staging and gated in production (see production.py).
API_DOCS_ENABLED = env.bool("API_DOCS_ENABLED", default=True)
{%- endif %}
{% if cookiecutter.countries_app == "yes" %}

# Countries -----------------------------------------------------------------------
CITIES_LIGHT_APP_NAME = "cities"
{%- if cookiecutter.languages == "en_ar" %}
CITIES_LIGHT_TRANSLATION_LANGUAGES = ["ar", "en"]
{%- else %}
CITIES_LIGHT_TRANSLATION_LANGUAGES = ["en"]
{%- endif %}
CITIES_LIGHT_INCLUDE_COUNTRIES = None
{%- endif %}


# Admin ------------------------------------------------------------------------

# The admin is not mounted at /admin/. This is defence in depth (it removes scanner
# noise), never a substitute for 2FA, lockout or TLS.
ADMIN_URL_PREFIX = "{{ cookiecutter.admin_url_prefix }}"

UNFOLD = {
    "SITE_TITLE": SITE_NAME,
    "SITE_HEADER": "{{ cookiecutter.client_name }}",
    "SITE_SUBHEADER": "{{ cookiecutter.project_name }}",
    "SHOW_HISTORY": True,
    "SHOW_VIEW_ON_SITE": True,
    "COLORS": {
        # Replace with the client's brand palette (RGB triplets, no commas).
        "primary": {
            "50": "240 249 255",
            "100": "224 242 254",
            "200": "186 230 253",
            "300": "125 211 252",
            "400": "56 189 248",
            "500": "14 165 233",
            "600": "2 132 199",
            "700": "3 105 161",
            "800": "7 89 133",
            "900": "12 74 110",
            "950": "8 47 73",
        },
    },
}
{% if cookiecutter.sentry == "yes" %}

# Error monitoring ---------------------------------------------------------------
# Initialised only when SENTRY_DSN is provided. Without it Sentry stays fully
# disabled: no init, no network calls.

SENTRY_DSN = env("SENTRY_DSN", default="")
if SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[DjangoIntegration()],
        environment=env("SENTRY_ENVIRONMENT", default="development"),
        release=env("SENTRY_RELEASE", default=None),
        traces_sample_rate=env.float("SENTRY_TRACES_SAMPLE_RATE", default=0.0),
        send_default_pii=env.bool("SENTRY_SEND_DEFAULT_PII", default=False),
    )
{%- endif %}


# Logging ------------------------------------------------------------------------
# Never log secrets, tokens, session keys or personal data. See
# monitoring-and-logging.md in the KUWAITNET web standards.

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {name} {process:d} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "verbose"},
    },
    "root": {"handlers": ["console"], "level": env("LOG_LEVEL", default="INFO")},
    "loggers": {
        "django.security": {"handlers": ["console"], "level": "WARNING", "propagate": False},
{%- if cookiecutter.rate_limiting == "yes" %}
        "axes": {"handlers": ["console"], "level": "WARNING", "propagate": False},
{%- endif %}
        "{{ cookiecutter.project_slug }}": {
            "handlers": ["console"],
            "level": env("LOG_LEVEL", default="INFO"),
            "propagate": False,
        },
    },
}
