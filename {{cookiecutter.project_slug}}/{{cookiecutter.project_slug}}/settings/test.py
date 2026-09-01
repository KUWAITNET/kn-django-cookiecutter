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

# Rebinds rather than mutates, because a star import shares the dict with
# settings/base.py: mutating it here would rewrite what the project ships, and
# apps/core/tests/test_storage.py reads base to assert exactly that. Replacing the
# whole entry rather than its BACKEND matters too - a cloud staticfiles entry
# carries OPTIONS that the plain storage class would reject.
STORAGES = {  # noqa: F405
    **STORAGES,  # noqa: F405
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
{%- if cookiecutter.asset_pipeline == "compressor" %}

# Compression is a build step, and rendering it per test would only measure rcssmin.
COMPRESS_ENABLED = False
COMPRESS_OFFLINE = False
{%- endif %}

CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
{%- if cookiecutter.task_queue == "huey" %}

# Tasks run inline, in this process, against an in-memory store: the suite tests
# what the task does, not that huey can talk to {% if cookiecutter.huey_backend == "postgres" %}Postgres{% elif cookiecutter.huey_backend == "redis" %}Redis{% else %}SQLite{% endif %}. Rebinds rather than
# mutates, because a star import shares the dict with settings/base.py.
HUEY = {**HUEY, "immediate": True}  # noqa: F405
{%- elif cookiecutter.task_queue == "celery" %}

# Tasks run inline, in this process, with no broker: the suite tests what the task
# does, not that Celery can reach {% if cookiecutter.task_broker == "redis" %}Redis{% elif cookiecutter.task_broker == "rabbitmq" %}RabbitMQ{% else %}SQS{% endif %}. EAGER_PROPAGATES means a task that
# raises fails the test instead of being swallowed into a result.
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
{%- endif %}

DATABASES["default"] = env.db(  # noqa: F405
    "TEST_DATABASE_URL",
    default=env(  # noqa: F405
        "DATABASE_URL",
        default="postgres://postgres:postgres@localhost:5432/{{ cookiecutter.project_slug }}",
    ),
)

MEDIA_ROOT = os.path.join(BASE_DIR, ".test-media")  # noqa: F405
PRIVATE_MEDIA_ROOT = os.path.join(BASE_DIR, ".test-private-media")  # noqa: F405
{%- if cookiecutter.media_storage != "filesystem" %}

# The suite runs with no cloud credentials and no network - a test that needs a
# real bucket is an integration test, not a unit test - so both media storages go
# back to local directories here. The backend the project actually ships is
# asserted against the base settings module in apps/core/tests/test_storage.py,
# which is the only place that can check it without reaching the network.
STORAGES = {  # noqa: F405
    **STORAGES,  # noqa: F405
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
        "OPTIONS": {"location": MEDIA_ROOT, "base_url": MEDIA_URL},  # noqa: F405
    },
    # Not a plain FileSystemStorage: this one keeps the real private storage's
    # refusal to build a URL, which is the behaviour the suite is there to guard.
    "private_media": {
        "BACKEND": "apps.core.storage.PrivateFileSystemStorage",
        "OPTIONS": {"location": PRIVATE_MEDIA_ROOT},
    },
}
{%- endif %}
