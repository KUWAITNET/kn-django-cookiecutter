"""Base settings for {{ cookiecutter.project_name }}.

Configuration is environment-driven (12-factor) via django-environ. Secrets and
per-environment values come from the process environment or a local ``.env`` file
(see ``.env.example``). The ``dev``, ``production`` and ``test`` modules import from
here and override.

Production deliberately provides NO fallback for secrets, so a misconfigured deploy
fails loudly at boot rather than silently running with a development key.
"""

import os
{% if cookiecutter.api != "none" or cookiecutter.media_storage == "gcs" %}from datetime import timedelta
{% endif %}
import environ
{%- if cookiecutter.task_queue == "celery" %}
from celery.schedules import crontab
{%- endif %}
from django.utils.csp import CSP

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
{%- if cookiecutter.countries_app == "cities" %}
    "cities_light",
{%- elif cookiecutter.countries_app == "django_countries" %}
    "django_countries",
{%- endif %}
{%- if cookiecutter.countries_app != "none" or cookiecutter.forms_suite == "yes" %}
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
    "auditlog",
    # Site-wide configuration as a single row. Provides no models of its own; the
    # project's singleton lives in apps.core.models.
    "solo",
{%- if cookiecutter.task_queue == "huey" %}
    # Provides 'manage.py run_huey' (the consumer) and the decorators in
    # apps/tasks/tasks.py. Importing it is what builds the HUEY object below.
    "huey.contrib.djhuey",
{%- endif %}
    # Installed in every environment, not just development: shell_plus, show_urls
    # and graph_models are as useful on a server as locally, and an app that is
    # only present in development is an app that breaks production at startup.
    # runserver_plus needs Werkzeug, which is deliberately not a dependency.
    "django_extensions",
{%- if cookiecutter.asset_pipeline == "compressor" %}
    "compressor",
{%- endif %}
{%- if cookiecutter.api != "none" %}
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "drf_spectacular",
    "drf_standardized_errors",
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
{%- if cookiecutter.task_queue != "none" %}
    "apps.tasks",
{%- endif %}
{%- if cookiecutter.countries_app == "cities" %}
    "apps.cities",
{%- endif %}
{%- if cookiecutter.notifications_app == "yes" %}
    "apps.notifications",
{%- endif %}
{%- if cookiecutter.stack == "wagtail" %}
    "apps.navigation",
    "apps.home",
{%- if cookiecutter.newsroom == "yes" %}
    "apps.newsroom",
{%- endif %}
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
    "apps.core.middleware.NonLocalisedPathLocaleMiddleware",
{%- endif %}
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    # Must follow AuthenticationMiddleware: it reads request.user to attribute
    # each change to a person. Without it entries are recorded with no actor.
    "auditlog.middleware.AuditlogMiddleware",
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
    "django.middleware.csp.ContentSecurityPolicyMiddleware",
    # After the CSP middleware, so it can hand it the Django admin's policy.
    "apps.core.csp.DjangoAdminCSPMiddleware",
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
                # Supplies the csp_nonce template variable. Django keeps the
                # nonce private on the request, so without this processor every
                # inline script loses its nonce silently and the browser drops it.
                "django.template.context_processors.csp",
{%- if cookiecutter.stack == "wagtail" %}
                "wagtail.contrib.settings.context_processors.settings",
{%- if cookiecutter.multisite == "multi" %}
                "apps.navigation.context_processors.site_switcher",
{%- endif %}
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
{%- if cookiecutter.use_2fa == "yes" %}

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

{%- if cookiecutter.languages == "en_ar" %}
# Paths that must NOT be redirected to a language-prefixed URL. Django's
# LocaleMiddleware turns a 404 on an unprefixed path into a 302; for machine
# endpoints that converts an honest "not found" into a redirect an API client
# cannot interpret. See apps.core.middleware.
LOCALE_REDIRECT_EXEMPT_PREFIXES = [
{%- if cookiecutter.api != "none" %}
    "/api/",
{%- endif %}
    "/healthz",
    "/robots.txt",
    "/sitemap.xml",
    # RFC 9116 names exactly one location, and researchers and scanners request
    # it verbatim. Redirecting it into /en/ makes it 404 for every caller that
    # matters, which looks like "they publish no contact".
    "/.well-known/",
    "/private-media/",
]
{%- endif %}

TIME_ZONE = "{{ cookiecutter.timezone }}"
USE_I18N = True
USE_TZ = True


# Static and media -------------------------------------------------------------

STATICFILES_FINDERS = [
    "django.contrib.staticfiles.finders.FileSystemFinder",
    "django.contrib.staticfiles.finders.AppDirectoriesFinder",
{%- if cookiecutter.asset_pipeline == "compressor" %}
    # Serves the compressed output back to collectstatic and to the dev server.
    "compressor.finders.CompressorFinder",
{%- endif %}
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
{%- if cookiecutter.media_storage == "filesystem" %}

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    # Personal data. A named entry rather than a bare instance so that the test
    # settings - and a future migration to a bucket - can repoint it in one place.
    "private_media": {"BACKEND": "apps.core.storage.PrivateMediaStorage"},
    "staticfiles": {
        # Hashed filenames: cache-busting without hand-stamped ?v= query strings.
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}
{%- else %}


# Object storage ---------------------------------------------------------------
#
# TWO media storages, never one. Editorial media (page images, brochures) is
# public; anything a visitor uploads about themselves - a CV, an ID copy, a form
# attachment - goes to the private storage and is reachable only through
# apps.core.views.serve_private_file, which checks a permission first. That is the
# same split the filesystem build makes with MEDIA_ROOT and PRIVATE_MEDIA_ROOT.
#
# The bucket is NOT public-read: no public ACL is ever sent, and the URLs the
# storage builds are signed and expire. Making the bucket world-readable would
# turn every private object into a public document the moment its key is guessed
# or logged - which is exactly how applicant CVs leaked in the reference project.
MEDIA_LOCATION = env("MEDIA_LOCATION", default="media")
PRIVATE_MEDIA_LOCATION = env("PRIVATE_MEDIA_LOCATION", default="private")
{%- if cookiecutter.static_storage == "cloud" %}
STATIC_LOCATION = env("STATIC_LOCATION", default="static")
{%- endif %}

# How a private file reaches the browser.
#
# Default (False): the file is STREAMED through serve_private_file, so the
# permission is checked on every single byte and no URL exists that could be
# forwarded, logged by a proxy, or pasted into a ticket.
#
# True: the view redirects to a short-lived signed URL instead. That is cheaper -
# the bytes go straight from the bucket, with no worker held open for a 200 MB
# download - but the trade-off is real: once issued, a signed URL is valid for its
# whole lifetime to ANYONE holding it. It keeps working after the user logs out,
# after the permission is revoked, and after the link is forwarded. Turn it on
# only for large files, and set the expiry as low as the download will tolerate.
PRIVATE_MEDIA_SIGNED_URLS = env.bool("PRIVATE_MEDIA_SIGNED_URLS", default=False)
PRIVATE_MEDIA_URL_EXPIRE_SECONDS = env.int("PRIVATE_MEDIA_URL_EXPIRE_SECONDS", default=300)
{%- if cookiecutter.media_storage == "s3" %}

AWS_STORAGE_BUCKET_NAME = env("AWS_STORAGE_BUCKET_NAME", default="")
# Personal data in a bucket of its own is the strongest form of the split: a
# bucket policy, not a key prefix, is what stands between public and private.
# Defaults to the same bucket, where the prefixes do the separating.
AWS_PRIVATE_STORAGE_BUCKET_NAME = env(
    "AWS_PRIVATE_STORAGE_BUCKET_NAME", default=AWS_STORAGE_BUCKET_NAME
)
AWS_S3_REGION_NAME = env("AWS_S3_REGION_NAME", default="")
# Unset on a host with an instance role / IRSA, which is preferred: no long-lived
# key to rotate, leak or commit.
AWS_ACCESS_KEY_ID = env("AWS_ACCESS_KEY_ID", default="")
AWS_SECRET_ACCESS_KEY = env("AWS_SECRET_ACCESS_KEY", default="")
# Set only for an S3-compatible store (MinIO, DigitalOcean Spaces, Wasabi).
AWS_S3_ENDPOINT_URL = env("AWS_S3_ENDPOINT_URL", default="") or None
# A CDN in front of the PUBLIC prefix. Never used for private media.
AWS_S3_CUSTOM_DOMAIN = env("AWS_S3_CUSTOM_DOMAIN", default="") or None
AWS_QUERYSTRING_EXPIRE = env.int("AWS_QUERYSTRING_EXPIRE", default=3600)
{%- if cookiecutter.static_storage == "cloud" %}
# Static files are public; media is not. On S3 a prefix-scoped bucket policy can
# express that inside one bucket, so this defaults to the media bucket - but a
# separate bucket keeps the public grant physically away from the private data.
AWS_STATIC_BUCKET_NAME = env("AWS_STATIC_BUCKET_NAME", default=AWS_STORAGE_BUCKET_NAME)
{%- endif %}

_S3_COMMON = {
    "bucket_name": AWS_STORAGE_BUCKET_NAME,
    "region_name": AWS_S3_REGION_NAME or None,
    "access_key": AWS_ACCESS_KEY_ID or None,
    "secret_key": AWS_SECRET_ACCESS_KEY or None,
    "endpoint_url": AWS_S3_ENDPOINT_URL,
    # Required in every region opened since 2014, and harmless in the older ones.
    "signature_version": "s3v4",
    # None means "send no ACL header at all" - never "public-read". Buckets created
    # with object ownership set to "bucket owner enforced" reject any ACL, so a
    # value here is both a security hole and a runtime error waiting to happen.
    "default_acl": None,
    # Upload names are generated UUIDs, so a collision means something is wrong:
    # keep both files rather than silently destroy the first.
    "file_overwrite": False,
}

STORAGES = {
    "default": {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            **_S3_COMMON,
            "location": MEDIA_LOCATION,
            # Signed URLs even for editorial media, because the bucket is not
            # public-read. Put a CDN in front (AWS_S3_CUSTOM_DOMAIN) with origin
            # access control if permanent, cacheable URLs are needed.
            "querystring_auth": True,
            "querystring_expire": AWS_QUERYSTRING_EXPIRE,
            "custom_domain": AWS_S3_CUSTOM_DOMAIN,
        },
    },
    "private_media": {
        "BACKEND": "apps.core.storage.PrivateMediaStorage",
        "OPTIONS": {
            **_S3_COMMON,
            "bucket_name": AWS_PRIVATE_STORAGE_BUCKET_NAME,
            "location": PRIVATE_MEDIA_LOCATION,
            "querystring_auth": True,
            "querystring_expire": PRIVATE_MEDIA_URL_EXPIRE_SECONDS,
            # Never a CDN for private media: an edge cache is a copy of the file
            # sitting outside every permission check.
            "custom_domain": None,
        },
    },
{%- if cookiecutter.static_storage == "cloud" %}
    "staticfiles": {
        "BACKEND": "apps.core.storage.StaticCloudStorage",
        "OPTIONS": {
            **_S3_COMMON,
            "bucket_name": AWS_STATIC_BUCKET_NAME,
            "location": STATIC_LOCATION,
            # The site's own CSS and JS: public by definition, and their URLs are
            # baked into a manifest and into compiled CSS, so they must not expire.
            # This prefix - and only this prefix - carries a public-read bucket
            # policy, or sits behind a CDN.
            "querystring_auth": False,
            "custom_domain": AWS_S3_CUSTOM_DOMAIN,
            # Content-hashed names, so overwriting is a no-op rather than a risk.
            "file_overwrite": True,
        },
    },
{%- else %}
    "staticfiles": {
        # Hashed filenames: cache-busting without hand-stamped ?v= query strings.
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
{%- endif %}
}
{%- elif cookiecutter.media_storage == "gcs" %}

GS_BUCKET_NAME = env("GS_BUCKET_NAME", default="")
# Personal data in a bucket of its own is the strongest form of the split: an IAM
# policy, not a key prefix, is what stands between public and private. Defaults to
# the same bucket, where the prefixes do the separating.
GS_PRIVATE_BUCKET_NAME = env("GS_PRIVATE_BUCKET_NAME", default=GS_BUCKET_NAME)
GS_PROJECT_ID = env("GS_PROJECT_ID", default="")
# Path to a service-account key file. Unset on a host using workload identity or
# the metadata server, which is preferred: no key file to rotate, leak or commit.
# google-cloud-storage reads this variable itself; it is named here so the
# deployment check in apps/core/checks.py can see whether credentials exist.
GOOGLE_APPLICATION_CREDENTIALS = env("GOOGLE_APPLICATION_CREDENTIALS", default="")
GS_EXPIRATION_SECONDS = env.int("GS_EXPIRATION_SECONDS", default=3600)
# Set only for a GCS-compatible emulator or a private service endpoint.
GS_CUSTOM_ENDPOINT = env("GS_CUSTOM_ENDPOINT", default="") or None
{%- if cookiecutter.static_storage == "cloud" %}
# Static files are public; media is not. GCS IAM is per bucket and uniform
# bucket-level access disables object ACLs, so a public prefix inside a private
# bucket is not expressible: static files need a bucket of their own.
GS_STATIC_BUCKET_NAME = env("GS_STATIC_BUCKET_NAME", default=GS_BUCKET_NAME)
{%- endif %}

_GS_COMMON = {
    "bucket_name": GS_BUCKET_NAME,
    "project_id": GS_PROJECT_ID or None,
    # None means "apply the bucket's own uniform access, send no ACL" - never
    # "publicRead". Buckets with uniform bucket-level access reject object ACLs
    # outright, so a value here is both a security hole and a runtime error.
    "default_acl": None,
    # Upload names are generated UUIDs, so a collision means something is wrong:
    # keep both files rather than silently destroy the first.
    "file_overwrite": False,
    "custom_endpoint": GS_CUSTOM_ENDPOINT,
}

STORAGES = {
    "default": {
        "BACKEND": "storages.backends.gcloud.GoogleCloudStorage",
        "OPTIONS": {
            **_GS_COMMON,
            "location": MEDIA_LOCATION,
            # Signed URLs even for editorial media, because the bucket is not
            # public-read. Put Cloud CDN in front of it if permanent, cacheable
            # URLs are needed.
            "querystring_auth": True,
            "expiration": timedelta(seconds=GS_EXPIRATION_SECONDS),
        },
    },
    "private_media": {
        "BACKEND": "apps.core.storage.PrivateMediaStorage",
        "OPTIONS": {
            **_GS_COMMON,
            "bucket_name": GS_PRIVATE_BUCKET_NAME,
            "location": PRIVATE_MEDIA_LOCATION,
            "querystring_auth": True,
            "expiration": timedelta(seconds=PRIVATE_MEDIA_URL_EXPIRE_SECONDS),
        },
    },
{%- if cookiecutter.static_storage == "cloud" %}
    "staticfiles": {
        "BACKEND": "apps.core.storage.StaticCloudStorage",
        "OPTIONS": {
            **_GS_COMMON,
            "bucket_name": GS_STATIC_BUCKET_NAME,
            "location": STATIC_LOCATION,
            # The site's own CSS and JS: public by definition, and their URLs are
            # baked into a manifest and into compiled CSS, so they must not expire.
            # This prefix - and only this prefix - is granted public read.
            "querystring_auth": False,
            # Content-hashed names, so overwriting is a no-op rather than a risk.
            "file_overwrite": True,
        },
    },
{%- else %}
    "staticfiles": {
        # Hashed filenames: cache-busting without hand-stamped ?v= query strings.
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
{%- endif %}
}
{%- else %}

AZURE_ACCOUNT_NAME = env("AZURE_ACCOUNT_NAME", default="")
# Unset on a host using a managed identity, which is preferred: no long-lived
# key to rotate, leak or commit.
AZURE_ACCOUNT_KEY = env("AZURE_ACCOUNT_KEY", default="")
AZURE_CONNECTION_STRING = env("AZURE_CONNECTION_STRING", default="")
AZURE_CONTAINER = env("AZURE_CONTAINER", default="")
# Personal data in a container of its own is the strongest form of the split:
# public access is a per-container setting in Azure, so a separate container is
# what makes "private" structural rather than conventional.
AZURE_PRIVATE_CONTAINER = env("AZURE_PRIVATE_CONTAINER", default=AZURE_CONTAINER)
AZURE_URL_EXPIRATION_SECS = env.int("AZURE_URL_EXPIRATION_SECS", default=3600)
# A CDN in front of the PUBLIC container. Never used for private media.
AZURE_CUSTOM_DOMAIN = env("AZURE_CUSTOM_DOMAIN", default="") or None
{%- if cookiecutter.static_storage == "cloud" %}
# Static files are public; media is not. Public access is a per-container setting
# in Azure, with no per-object override, so static files need a container of their
# own - the one place anonymous blob read is switched on.
AZURE_STATIC_CONTAINER = env("AZURE_STATIC_CONTAINER", default=AZURE_CONTAINER)
{%- endif %}

_AZURE_COMMON = {
    "account_name": AZURE_ACCOUNT_NAME or None,
    "account_key": AZURE_ACCOUNT_KEY or None,
    "connection_string": AZURE_CONNECTION_STRING or None,
    # Upload names are generated UUIDs, so a collision means something is wrong:
    # keep both files rather than silently destroy the first.
    "overwrite_files": False,
}

STORAGES = {
    "default": {
        "BACKEND": "storages.backends.azure_storage.AzureStorage",
        "OPTIONS": {
            **_AZURE_COMMON,
            "azure_container": AZURE_CONTAINER,
            "location": MEDIA_LOCATION,
            # Azure has no per-object ACL: a container is public or it is not, and
            # this one is not. expiration_secs is what makes every URL a
            # short-lived SAS; leaving it None would emit a bare blob URL that only
            # works if the container was opened to the world.
            "expiration_secs": AZURE_URL_EXPIRATION_SECS,
            "custom_domain": AZURE_CUSTOM_DOMAIN,
        },
    },
    "private_media": {
        "BACKEND": "apps.core.storage.PrivateMediaStorage",
        "OPTIONS": {
            **_AZURE_COMMON,
            "azure_container": AZURE_PRIVATE_CONTAINER,
            "location": PRIVATE_MEDIA_LOCATION,
            "expiration_secs": PRIVATE_MEDIA_URL_EXPIRE_SECONDS,
            # Never a CDN for private media: an edge cache is a copy of the file
            # sitting outside every permission check.
            "custom_domain": None,
        },
    },
{%- if cookiecutter.static_storage == "cloud" %}
    "staticfiles": {
        "BACKEND": "apps.core.storage.StaticCloudStorage",
        "OPTIONS": {
            **_AZURE_COMMON,
            "azure_container": AZURE_STATIC_CONTAINER,
            "location": STATIC_LOCATION,
            # The site's own CSS and JS: public by definition, and their URLs are
            # baked into a manifest and into compiled CSS, so they must not expire.
            # This container - and only this container - is opened for blob read.
            "expiration_secs": None,
            "custom_domain": AZURE_CUSTOM_DOMAIN,
            # Content-hashed names, so overwriting is a no-op rather than a risk.
            "overwrite_files": True,
        },
    },
{%- else %}
    "staticfiles": {
        # Hashed filenames: cache-busting without hand-stamped ?v= query strings.
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
{%- endif %}
}
{%- endif %}
{%- endif %}
{%- if cookiecutter.asset_pipeline == "compressor" %}


# Asset pipeline (django-compressor) --------------------------------------------
#
# WhiteNoise already gzips, brotlis and cache-busts, so this exists for the case it
# does not cover: a SASS/LESS theme compiled without a Node toolchain, via
# COMPRESS_PRECOMPILERS. See docs/14-decisions.md.
COMPRESS_ENABLED = env.bool("COMPRESS_ENABLED", default=not DEBUG)
# Offline only in production, where the build step runs. Rendering with
# COMPRESS_OFFLINE on and no manifest raises on every page, which is the right
# failure - but it must not happen in development or in the test suite.
COMPRESS_OFFLINE = False
COMPRESS_FILTERS = {
    "css": [
        # Rewrites url() references to absolute paths before concatenation, which
        # is the whole reason a naive "cat *.css" breaks background images.
        "compressor.filters.css_default.CssAbsoluteFilter",
        "compressor.filters.cssmin.rCSSMinFilter",
    ],
    "js": ["compressor.filters.jsmin.rJSMinFilter"],
}
{%- if cookiecutter.static_storage == "cloud" %}
# Compressed output belongs next to the static files it references, in the bucket.
COMPRESS_STORAGE = "apps.core.storage.StaticCloudStorage"
{%- endif %}
{%- endif %}

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
#
# Django 6.1 deprecates these EMAIL_* settings in favour of MAILERS, and this
# block should move over - but not yet. django-post-office reads
# settings.EMAIL_BACKEND directly and calls get_connection(backend), both of
# which Django refuses once MAILERS is defined (AttributeError and RuntimeError
# respectively), so migrating early breaks every send in the project.
#
# The trigger is concrete: post_office merged MAILERS support one day after
# cutting 3.11.3, so the first release ABOVE 3.11.3 carries it. At that point
# raise the pin, define MAILERS, set POST_OFFICE["DEFAULT_MAILER"], and delete
# this block - POST_OFFICE["BACKENDS"] is ignored under MAILERS. Until then the
# deprecation warning on this setting is expected, and is the reason the test
# suite cannot yet run with RemovedInDjango70Warning as an error.

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

# Fallback meta description when a page supplies none.
SITE_DESCRIPTION = env("SITE_DESCRIPTION", default="")

# Search-console style verification tokens rendered into <head>.
SEO_SITE_VERIFICATION = env.list("SEO_SITE_VERIFICATION", default=[])
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

# Content-Security-Policy (Django built-in, 6.0+).
#
# Inline scripts use the per-request nonce ({% raw %}{{ csp_nonce }}{% endraw %}); there is no
# 'unsafe-inline' and no 'unsafe-eval' in script-src. If a vendored theme library
# needs eval, that is a finding to fix or a documented, time-boxed exception - not
# a permanent setting.
SECURE_CSP = {
    "default-src": ["'self'"],
    "script-src": [
        "'self'",
        # Replaced with the per-request nonce by the CSP middleware.
        CSP.NONCE,
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
{%- if cookiecutter.rate_limiting == "yes" and cookiecutter.frontend != "api_only" %}

# django-ratelimit budgets for non-DRF public POST endpoints. Endpoints that send
# e-mail or write files get the tightest budgets: each request costs an external
# resource.
# Fail CLOSED when the counter cannot be read. django-ratelimit already defaults
# to this, but it is written out because the consequence of the other value is
# severe and silent: with FAIL_OPEN, a Redis outage removes the rate limit from
# every endpoint that needed it most, and nothing in the logs says the protection
# is gone. A cache outage should cost availability, not the control.
RATELIMIT_FAIL_OPEN = False

RATELIMIT_FORM_SUBMIT = env("RATELIMIT_FORM_SUBMIT", default="5/h")
RATELIMIT_NEWSLETTER = env("RATELIMIT_NEWSLETTER", default="3/h")
RATELIMIT_SEARCH = env("RATELIMIT_SEARCH", default="30/m")
{%- endif %}


# Security contact -------------------------------------------------------------

# Where a vulnerability report should go (RFC 9116, /.well-known/security.txt).
# A monitored address, not an individual: a personal mailbox stops being read the
# day that person changes role, and the file is public for years.
# Unconditional on purpose: apps.core.views.security_txt reads it whatever the
# generation options were, and it once sat inside the rate-limiting block.
SECURITY_CONTACT_EMAIL = env("SECURITY_CONTACT_EMAIL", default="{{ cookiecutter.author_email }}")


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
{%- if cookiecutter.api != "none" %}


# API ---------------------------------------------------------------------------
# Implements api-standard.md. Deny by default; public endpoints opt in explicitly.

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    # drf-standardized-errors' AutoSchema, not drf-spectacular's: it is the
    # subclass that adds the error responses to every operation.
    "DEFAULT_SCHEMA_CLASS": "drf_standardized_errors.openapi.AutoSchema",
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
    # Single error envelope: RFC 9457 application/problem+json. This must name
    # the package's own function and nothing else - the schema generator compares
    # the view's handler against it by identity, and a wrapper of our own would
    # silently switch every generated error response back off. The project's
    # behaviour is injected through DRF_STANDARDIZED_ERRORS below instead.
    "EXCEPTION_HANDLER": "drf_standardized_errors.handler.exception_handler",
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

# drf-standardized-errors owns exception coverage; apps/api/exceptions.py owns
# the wire format. ERROR_SCHEMAS replaces the package's own response schemas with
# the RFC 9457 ones, so the documented shape and the shipped shape are the same
# thing. ENABLE_IN_DEBUG_FOR_UNHANDLED_EXCEPTIONS stays off deliberately: with
# DEBUG on, a bug should show its traceback rather than a tidy 500 body.
DRF_STANDARDIZED_ERRORS = {
    "EXCEPTION_HANDLER_CLASS": "apps.api.exceptions.ProblemDetailExceptionHandler",
    "EXCEPTION_FORMATTER_CLASS": "apps.api.exceptions.ProblemDetailExceptionFormatter",
    "ERROR_SCHEMAS": {
        "400": "apps.api.serializers.ValidationProblemDetailSerializer",
        "401": "apps.api.serializers.ProblemDetailSerializer",
        "403": "apps.api.serializers.ProblemDetailSerializer",
        "404": "apps.api.serializers.ProblemDetailSerializer",
        "405": "apps.api.serializers.ProblemDetailSerializer",
        "406": "apps.api.serializers.ProblemDetailSerializer",
        "415": "apps.api.serializers.ProblemDetailSerializer",
        "429": "apps.api.serializers.ThrottledProblemDetailSerializer",
        "500": "apps.api.serializers.ProblemDetailSerializer",
    },
}

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
    # drf-standardized-errors' copy of drf-spectacular's enum hook. It behaves
    # identically except that it leaves the error components alone, where the
    # same choice set legitimately appears under several names.
    "POSTPROCESSING_HOOKS": ["drf_standardized_errors.openapi_hooks.postprocess_schema_enums"],
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
{%- if cookiecutter.countries_app != "none" %}


# Countries -----------------------------------------------------------------------
# Whichever backend is selected, apps.core.countries is the only module the rest of
# the project talks to, so a form or a serializer never learns which one this is.
{%- if cookiecutter.countries_app == "cities" %}
CITIES_LIGHT_APP_NAME = "cities"
{%- endif %}

# Countries withheld from public choice lists, as ISO 3166-1 alpha-2 codes.
# Env-driven so the policy is configuration rather than a literal buried in a
{%- if cookiecutter.countries_app == "cities" %}
# queryset: Country.objects.selectable() is the only reader.
{%- else %}
# queryset. Normally empty on this backend: the KUWAITNET django-countries fork
# already applies the country-list policy to the data it ships, so there is
# nothing left for a runtime filter to remove. It stays available for the
# per-client exclusions a commercial decision produces later.
{%- endif %}
COUNTRY_EXCLUDED_CODES = env.list("COUNTRY_EXCLUDED_CODES", default=[])
{%- if cookiecutter.countries_app == "cities" %}

# The concrete country/region/city models live in apps.cities, so cities_light's
# own migrations must not run: they would try to alter models that no longer
# exist in this project and abort the migrate with
# "Region has no field named 'country'". Required by django-cities-light whenever
# CITIES_LIGHT_APP_NAME is customised.
MIGRATION_MODULES = {"cities_light": None}
{%- if cookiecutter.languages == "en_ar" %}
CITIES_LIGHT_TRANSLATION_LANGUAGES = ["ar", "en"]
{%- else %}
CITIES_LIGHT_TRANSLATION_LANGUAGES = ["en"]
{%- endif %}
CITIES_LIGHT_INCLUDE_COUNTRIES = None
{%- endif %}
{%- endif %}


# Audit trail ------------------------------------------------------------------
# Who changed what, when - the questionnaire's "activity and audit logs for
# administrator actions". This is an audit trail, NOT a revisions system: it
# records field-level diffs, so a change can be reconstructed, but it does not
# offer one-click rollback the way page revisions do.
#
# Models are listed explicitly rather than tracking everything: an audit log that
# records every session and every rendition row is one nobody reads, and it grows
# without limit. Add editorially-owned and personal-data models here.
#
# Retention is at least 12 months (security baseline). Prune older entries with a
# scheduled job rather than letting the table grow forever.
{%- if cookiecutter.forms_suite == "yes" or cookiecutter.newsletter == "yes" or cookiecutter.notifications_app == "yes" or cookiecutter.countries_app == "cities" %}
AUDITLOG_INCLUDE_TRACKING_MODELS = (
{%- if cookiecutter.forms_suite == "yes" %}
    # exclude_fields matters here: without it the audit table stores a second
    # copy of the visitor's message and contact details, so a table created for
    # accountability quietly becomes another place personal data has to be
    # found, secured and erased. We record THAT a submission changed and who
    # changed it, not the contents again.
    {
        "model": "contact.ContactSubmission",
        "exclude_fields": ["message", "attachment", "phone", "email", "full_name"],
    },
{%- endif %}
{%- if cookiecutter.newsletter == "yes" %}
    {"model": "newsletter.Subscriber", "exclude_fields": ["unsubscribe_token"]},
{%- endif %}
{%- if cookiecutter.notifications_app == "yes" %}
    # Editorial content, not personal data: track it in full, because "who
    # changed the wording of the e-mail customers receive" is the question this
    # log exists to answer.
    "notifications.NotificationTemplate",
    "notifications.NotificationRecipient",
{%- endif %}
{%- if cookiecutter.countries_app == "cities" %}
    "cities.Country",
{%- endif %}
)
{%- else %}
AUDITLOG_INCLUDE_TRACKING_MODELS = ()
{%- endif %}
{%- if cookiecutter.task_queue != "none" %}

# How long an audit entry is kept before apps.tasks prunes it. The security
# baseline sets the floor at 12 months; the default is a little over that so a
# prune job that misses a few weeks does not immediately breach the policy.
AUDITLOG_RETENTION_DAYS = env.int("AUDITLOG_RETENTION_DAYS", default=400)
{%- endif %}
{%- if cookiecutter.task_queue == "huey" %}


# Background tasks ---------------------------------------------------------------
# Huey. One consumer process runs both the queue and the schedule - there is no
# separate beat process to forget on a new server.
#
# The consumer is a SECOND process running the same code as the web application. A
# deploy that restarts the web process and not the consumer leaves the old code
# running every scheduled job; see docs/07-deployment.md.

HUEY = {
    "name": "{{ cookiecutter.project_slug }}",
{%- if cookiecutter.huey_backend == "postgres" %}
    # The queue lives in the application database. No broker, no extra service to
    # deploy, monitor or back up - and the queue is inside the nightly dump with
    # everything else.
    "huey_class": "huey.PostgresHuey",
{%- elif cookiecutter.huey_backend == "redis" %}
    "huey_class": "huey.RedisHuey",
{%- else %}
    "huey_class": "huey.SqliteHuey",
{%- endif %}
    # Nothing in this project asks a task what it returned, and a result store is
    # one more thing to size and expire. Turn it on deliberately, per task.
    "results": False,
    "utc": True,
    # immediate = run the task inline, in the calling process, with no consumer at
    # all. On in development and under test so a task is just a function call; it
    # must be off wherever a consumer is actually running.
    "immediate": env.bool("HUEY_IMMEDIATE", default=DEBUG),
    "consumer": {
        "workers": env.int("HUEY_WORKERS", default=2),
        # Threads, not processes: these tasks are database and network bound, so
        # they spend their time waiting rather than holding the GIL.
        "worker_type": "thread",
        "periodic": True,
    },
{%- if cookiecutter.huey_backend == "postgres" %}
    "connection": {
        "dbname": DATABASES["default"]["NAME"],
        "user": DATABASES["default"]["USER"] or None,
        "password": DATABASES["default"]["PASSWORD"] or None,
        "host": DATABASES["default"]["HOST"] or None,
        "port": DATABASES["default"]["PORT"] or None,
        # Huey creates its own tables, and it would do so while this settings
        # module is being read. That would make 'manage.py check' require a live
        # database, which CI does not have. apps/tasks creates them on post_migrate
        # instead, so 'manage.py migrate' is still the only step anyone runs.
        "create_tables": False,
    },
{%- elif cookiecutter.huey_backend == "redis" %}
    # A different Redis database from the cache on purpose: flushing the cache is a
    # routine act, and it must not be able to empty the queue.
    "connection": {"url": env("HUEY_REDIS_URL", default="redis://127.0.0.1:6379/2")},
{%- else %}
    # Single-process, single-machine storage. Fine for development; see
    # docs/14-decisions.md before this reaches a server.
    "connection": {
        "filename": env("HUEY_SQLITE_PATH", default=os.path.join(BASE_DIR, "huey.sqlite3")),
    },
{%- endif %}
}
{%- elif cookiecutter.task_queue == "celery" %}


# Background tasks ---------------------------------------------------------------
# Celery. THREE processes in production, not one: the web application, a worker,
# and beat for the schedule. A deploy that restarts the web process and not the
# worker leaves the old code running every task; see docs/07-deployment.md.
#
# Everything below is read by {{ cookiecutter.project_slug }}/celery.py through the
# CELERY_ namespace, so the settings module stays the single source of truth.
{%- if cookiecutter.task_broker == "redis" %}

# Redis is not a durable message broker: an unpersisted restart drops whatever was
# queued, and there are no publisher confirms or dead-letter queues. Every task in
# this project must therefore be safe to lose and safe to run twice.
CELERY_BROKER_URL = env("CELERY_BROKER_URL", default="redis://127.0.0.1:6379/3")
{%- elif cookiecutter.task_broker == "rabbitmq" %}

# A real AMQP broker: durable queues, acknowledgements and dead-lettering. The
# credentials are the broker's own, so they rotate independently of everything else.
CELERY_BROKER_URL = env("CELERY_BROKER_URL", default="amqp://guest:guest@127.0.0.1:5672//")
{%- else %}

# Amazon SQS. "sqs://" with no credentials in the URL is deliberate: boto3 resolves
# them from the instance role (or the environment), so there is no broker password
# to store, rotate or leak. A local development machine normally overrides this with
# a redis:// URL - see docs/03-infrastructure.md for why that is acceptable for a
# queue and what must be re-tested against real SQS before go-live.
CELERY_BROKER_URL = env("CELERY_BROKER_URL", default="sqs://")
{%- endif %}

# One queue. Routing across several is exactly the complexity Celery was chosen for,
# but it is not free - add a queue when there is a task that must not wait behind
# another, and give the worker a matching -Q.
CELERY_TASK_DEFAULT_QUEUE = env(
    "CELERY_TASK_DEFAULT_QUEUE",
    default="{{ cookiecutter.project_slug }}",
)
{%- if cookiecutter.task_broker == "sqs" %}

if CELERY_BROKER_URL.startswith("sqs://"):
    CELERY_BROKER_TRANSPORT_OPTIONS = {
        "region": env("AWS_SQS_REGION", default="me-south-1"),
        # MUST be longer than the slowest task. SQS makes a message visible again
        # after this window whether or not the task is still running, so a task that
        # outlives it is delivered to a second worker and runs twice.
        "visibility_timeout": env.int("AWS_SQS_VISIBILITY_TIMEOUT", default=3600),
        # Namespaces the queues so several environments can share one account.
        "queue_name_prefix": env(
            "AWS_SQS_QUEUE_PREFIX",
            default="{{ cookiecutter.project_slug }}-",
        ),
        "polling_interval": env.float("AWS_SQS_POLLING_INTERVAL", default=1.0),
    }
    # Naming the queue URL outright lets the IAM policy drop ListQueues and
    # GetQueueUrl, so the worker can reach exactly one queue and discover nothing.
    _sqs_queue_url = env("AWS_SQS_QUEUE_URL", default="")
    if _sqs_queue_url:
        CELERY_BROKER_TRANSPORT_OPTIONS["predefined_queues"] = {
            CELERY_TASK_DEFAULT_QUEUE: {"url": _sqs_queue_url}
        }
{%- endif %}

# No result backend by default. Nothing here waits on a task's return value, and a
# result store is another datastore to size, expire and back up. Set
# CELERY_RESULT_BACKEND deliberately if a task ever needs to report back.
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", default="") or None
CELERY_TASK_IGNORE_RESULT = CELERY_RESULT_BACKEND is None

# Acknowledge a task AFTER it finishes, not when it is picked up, so a worker that
# is killed mid-task gives the task back to the queue instead of losing it. The
# price is that every task must be safe to run twice - which is the right
# constraint to design under anyway.
CELERY_TASK_ACKS_LATE = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1

# A task with no time limit is a worker that never comes back. The soft limit
# raises SoftTimeLimitExceeded inside the task so it can clean up; the hard limit
# kills the process.
CELERY_TASK_SOFT_TIME_LIMIT = env.int("CELERY_TASK_SOFT_TIME_LIMIT", default=300)
CELERY_TASK_TIME_LIMIT = env.int("CELERY_TASK_TIME_LIMIT", default=360)

# Run tasks inline in the calling process. Off in every deployed environment; the
# test settings turn it on so a task is just a function call.
CELERY_TASK_ALWAYS_EAGER = env.bool("CELERY_TASK_ALWAYS_EAGER", default=False)
CELERY_TASK_EAGER_PROPAGATES = True

CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_TIMEZONE = TIME_ZONE
CELERY_ENABLE_UTC = True

# The schedule lives here, in the repository, reviewed with the code that runs. It
# is deliberately NOT django-celery-beat: a schedule in database rows exists on one
# server, is absent from every code review, and is lost with the machine. The cost
# is that changing a time is a deploy. See docs/14-decisions.md.
#
# beat keeps its "when did I last run this" state in a small file. It must be on a
# writable, PERSISTENT path: delete it and every periodic task is treated as never
# run, so they all fire at once on the next start.
CELERY_BEAT_SCHEDULE_FILENAME = env(
    "CELERY_BEAT_SCHEDULE_FILENAME", default=os.path.join(BASE_DIR, "celerybeat-schedule")
)
CELERY_BEAT_SCHEDULE = {
    "prune-audit-log": {
        "task": "tasks.prune_audit_log",
        "schedule": crontab(hour=3, minute=30, day_of_week="sunday"),
    },
{%- if cookiecutter.notifications_app == "yes" %}
    "send-queued-mail": {
        "task": "tasks.send_queued_mail",
        "schedule": crontab(minute="*/10"),
    },
{%- endif %}
}
{%- endif %}

{%- if cookiecutter.use_2fa != "yes" or cookiecutter.rate_limiting != "yes" or cookiecutter.spam_protection == "none" %}

# Recorded exceptions to the security baseline ---------------------------------

# Each id below belongs to a check in apps/core/checks.py describing a control
# this project was generated WITHOUT. The check still exists and still says what
# is missing; this list is the acknowledgement that somebody chose it, and it is
# what a reviewer greps for when asking why the standard does not apply here.
#
# It is not a way to quieten a check you disagree with. Delete the entry the
# moment the control is turned on, and record the reason for every line that
# remains in docs/14-decisions.md - the go-live security pass asks for it.
SILENCED_SYSTEM_CHECKS = [
{%- if cookiecutter.use_2fa != "yes" %}
    "core.W007",  # no second factor on administrative accounts
{%- endif %}
{%- if cookiecutter.spam_protection == "none" %}
    "core.W008",  # no spam or bot protection on public forms
{%- endif %}
{%- if cookiecutter.rate_limiting != "yes" %}
    "core.W009",  # no rate limiting and no login lockout
{%- endif %}
]
{%- endif %}

# Admin ------------------------------------------------------------------------

# No admin is mounted at /admin/. This is defence in depth (it removes scanner
# noise), never a substitute for 2FA, lockout or TLS.
{%- if cookiecutter.stack == "wagtail" %}
# The two interfaces have independent prefixes - the Django admin is NOT a path
# under the Wagtail one - so the guess that finds the editors' login does not also
# hand over the second login form.
WAGTAIL_ADMIN_URL_PREFIX = env("WAGTAIL_ADMIN_URL_PREFIX", default="{{ cookiecutter.admin_url_prefix }}")
DJANGO_ADMIN_URL_PREFIX = env("DJANGO_ADMIN_URL_PREFIX", default="{{ cookiecutter.django_admin_url_prefix }}")

# Wagtail's login form is the one both admins share. Derived, never written out: a
# literal here outlives a prefix change and silently sends every @login_required
# redirect to a 404.
LOGIN_URL = f"/{WAGTAIL_ADMIN_URL_PREFIX}/login/"
{%- else %}
DJANGO_ADMIN_URL_PREFIX = env("DJANGO_ADMIN_URL_PREFIX", default="{{ cookiecutter.admin_url_prefix }}")

# Derived, never written out: a literal here outlives a prefix change and silently
# sends every @login_required redirect to a 404.
LOGIN_URL = f"/{DJANGO_ADMIN_URL_PREFIX}/login/"
{%- endif %}

# Site-wide configuration singleton (django-solo). The model is
# apps.core.models.{% if cookiecutter.stack == "wagtail" %}OperationalSettings{% else %}SiteConfiguration{% endif %}; it is read on{% if cookiecutter.stack == "wagtail" %}ce per request that needs it{% else %} every rendered page{% endif %},
# so the lookup is cached.
{%- if cookiecutter.cache == "redis" %}
# Redis is a SHARED cache, which is what makes this safe: django-solo refreshes the
# cached row on save, and every gunicorn worker sees that refresh. Caching the
# singleton in a per-process LocMemCache would instead leave the other workers
# serving the old values until the timeout expired - an edit that "did not save"
# on three page loads out of four. That is why this is enabled only here.
SOLO_CACHE = "default"
SOLO_CACHE_TIMEOUT = 60 * 60
SOLO_CACHE_PREFIX = "solo"
{%- else %}
# Deliberately NOT cached: this project's cache is per-process LocMemCache, and
# django-solo's cache refresh on save only reaches the worker that handled the
# save. The other workers would keep serving the old values until the timeout
# expired. One primary-key lookup per request is the cheaper mistake. Switch the
# cache to Redis and set SOLO_CACHE = "default" together, never separately.
SOLO_CACHE = None
{%- endif %}

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
{%- if cookiecutter.sentry == "yes" %}


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
