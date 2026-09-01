"""Test settings: fast, isolated, deterministic."""

from .base import *  # noqa: F403

DEBUG = False
SECRET_KEY = "django-insecure-test-key"  # noqa: S105
ALLOWED_HOSTS = ["*"]

# Fast hashing: the KDF is not under test.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
{% if cookiecutter.use_2fa == "yes" %}
# 2FA enrolment flows are exercised in dev and staging by real people, not here.
{%- if cookiecutter.stack == "wagtail" %}
WAGTAIL_2FA_REQUIRED = False
{%- else %}
OTP_ADMIN_REQUIRED = False
{%- endif %}
{% endif %}
{%- if cookiecutter.rate_limiting == "yes" %}
# Off by default so unrelated tests are not throttled. The rate-limiting tests
# re-enable it explicitly.
AXES_ENABLED = False
RATELIMIT_ENABLE = False
{% endif %}
# post_office wraps locmem, so django.core.mail.outbox populates as normal.
POST_OFFICE["BACKENDS"]["default"] = "django.core.mail.backends.locmem.EmailBackend"  # noqa: F405

STORAGES["staticfiles"]["BACKEND"] = (  # noqa: F405
    "django.contrib.staticfiles.storage.StaticFilesStorage"
)

CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}

DATABASES["default"] = env.db(  # noqa: F405
    "TEST_DATABASE_URL",
    default=env(  # noqa: F405
        "DATABASE_URL",
        default="postgres://postgres:postgres@localhost:5432/{{ cookiecutter.project_slug }}",
    ),
)

MEDIA_ROOT = os.path.join(BASE_DIR, ".test-media")  # noqa: F405
PRIVATE_MEDIA_ROOT = os.path.join(BASE_DIR, ".test-private-media")  # noqa: F405
