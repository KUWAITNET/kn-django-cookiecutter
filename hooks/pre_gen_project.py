"""Validate the selected options before any file is generated.

Cookiecutter aborts generation when this script exits non-zero, so every invalid
combination is caught here rather than producing a project that cannot start.
"""

import keyword
import re
import sys

STACK = "{{ cookiecutter.stack }}"
PROJECT_SLUG = "{{ cookiecutter.project_slug }}"
ADMIN_URL_PREFIX = "{{ cookiecutter.admin_url_prefix }}"
DJANGO_ADMIN_URL_PREFIX = "{{ cookiecutter.django_admin_url_prefix }}"
LANGUAGES = "{{ cookiecutter.languages }}"
FRONTEND = "{{ cookiecutter.frontend }}"
MULTISITE = "{{ cookiecutter.multisite }}"
API = "{{ cookiecutter.api }}"
CACHE = "{{ cookiecutter.cache }}"
DOCKER = "{{ cookiecutter.docker }}"
DEPLOY_TARGET = "{{ cookiecutter.deploy_target }}"
RATE_LIMITING = "{{ cookiecutter.rate_limiting }}"
SPAM_PROTECTION = "{{ cookiecutter.spam_protection }}"
USE_2FA = "{{ cookiecutter.use_2fa }}"
NEWSLETTER = "{{ cookiecutter.newsletter }}"
FORMS_SUITE = "{{ cookiecutter.forms_suite }}"
NOTIFICATIONS = "{{ cookiecutter.notifications_app }}"
DOMAIN_NAME = "{{ cookiecutter.domain_name }}"
PYTHON_VERSION = "{{ cookiecutter.python_version }}"
MEDIA_STORAGE = "{{ cookiecutter.media_storage }}"
STATIC_STORAGE = "{{ cookiecutter.static_storage }}"
ASSET_PIPELINE = "{{ cookiecutter.asset_pipeline }}"
TASK_QUEUE = "{{ cookiecutter.task_queue }}"
HUEY_BACKEND = "{{ cookiecutter.huey_backend }}"
TASK_BROKER = "{{ cookiecutter.task_broker }}"

errors: list[str] = []
warnings: list[str] = []


# --- Identifiers ------------------------------------------------------------

if not re.match(r"^[a-z][a-z0-9_]*$", PROJECT_SLUG):
    errors.append(
        f"project_slug {PROJECT_SLUG!r} is not a valid Python package name.\n"
        "    Use lowercase letters, digits and underscores, starting with a letter."
    )
elif keyword.iskeyword(PROJECT_SLUG):
    errors.append(f"project_slug {PROJECT_SLUG!r} is a Python keyword.")
elif PROJECT_SLUG in {"django", "wagtail", "apps", "test", "tests", "settings", "static", "media"}:
    errors.append(
        f"project_slug {PROJECT_SLUG!r} collides with a package or directory name the "
        "project itself uses. Choose a different name."
    )


# --- Admin URL prefixes -----------------------------------------------------

RESERVED_PREFIXES = {"api", "static", "media", "search", "accounts", "documents", "images"}


def check_prefix(name: str, value: str) -> None:
    """Validate one admin prefix, appending to the shared error list."""
    if not value:
        errors.append(f"{name} must not be empty.")
    elif value.strip("/") == "admin":
        errors.append(
            f"{name} must not be 'admin'.\n"
            "    The default admin path is the first thing automated scanners try. Choose a\n"
            "    project-specific prefix (see the security baseline, 'Administrative surface').\n"
            "    Note this is defence in depth, not a security control in its own right."
        )
    elif not re.match(r"^[a-z0-9][a-z0-9\-_]*$", value):
        errors.append(
            f"{name} {value!r} must be URL-safe: lowercase letters, "
            "digits, hyphens and underscores only, with no leading or trailing slash."
        )
    elif value in RESERVED_PREFIXES:
        errors.append(f"{name} {value!r} collides with another URL prefix used by the project.")


check_prefix("admin_url_prefix", ADMIN_URL_PREFIX)

if STACK == "wagtail":
    check_prefix("django_admin_url_prefix", DJANGO_ADMIN_URL_PREFIX)

    # Two admins on one prefix is the defect this pair of options exists to prevent:
    # the guess that finds the editors' login would hand over the second login form
    # as well, which is the whole of what a non-default prefix was meant to cost.
    if DJANGO_ADMIN_URL_PREFIX == ADMIN_URL_PREFIX:
        errors.append(
            f"django_admin_url_prefix {DJANGO_ADMIN_URL_PREFIX!r} is the same as "
            "admin_url_prefix. The two admins must answer on different paths."
        )
    elif DJANGO_ADMIN_URL_PREFIX.startswith(f"{ADMIN_URL_PREFIX}-") or ADMIN_URL_PREFIX.startswith(
        f"{DJANGO_ADMIN_URL_PREFIX}-"
    ):
        warnings.append(
            f"django_admin_url_prefix {DJANGO_ADMIN_URL_PREFIX!r} is derived from "
            f"admin_url_prefix {ADMIN_URL_PREFIX!r}. Anyone who finds one will try the "
            "other; prefer two unrelated words."
        )


# --- Stack layering: Wagtail-only options ------------------------------------

if STACK == "django":
    if MULTISITE == "multi":
        errors.append(
            "multisite='multi' is a Wagtail-only option.\n"
            "    Site scoping is built on Wagtail's Site model and site settings. For a plain\n"
            "    Django project, set multisite='single' and implement tenancy explicitly if the\n"
            "    project genuinely needs it."
        )
    if API == "headless":
        errors.append(
            "api='headless' is a Wagtail-only option.\n"
            "    'headless' means the Wagtail API v2 page/image/document endpoints. For a plain\n"
            "    Django project use api='rest', which ships the full DRF pack."
        )

if STACK == "wagtail" and FRONTEND == "api_only":
    errors.append(
        "frontend='api_only' is not available on the Wagtail stack.\n"
        "    A Wagtail CMS site serves pages. For a headless Wagtail backend use\n"
        "    stack='wagtail' with api='headless', which keeps the page templates available."
    )


# --- API-only coherence -----------------------------------------------------

if FRONTEND == "api_only":
    if API == "none":
        errors.append(
            "frontend='api_only' requires an API. Set api='rest', or choose\n"
            "    frontend='server_rendered'."
        )
    if FORMS_SUITE == "yes":
        errors.append(
            "forms_suite='yes' requires server-rendered templates.\n"
            "    Set forms_suite='no' for an API-only project; form handling belongs in the\n"
            "    API layer, where DRF serializers provide the equivalent validation."
        )
    if NEWSLETTER == "yes":
        errors.append(
            "newsletter='yes' requires server-rendered templates (subscribe and unsubscribe\n"
            "    pages). Set newsletter='no' for an API-only project."
        )


# --- Deployment coherence ---------------------------------------------------

if DEPLOY_TARGET == "docker_compose" and DOCKER == "no":
    errors.append(
        "deploy_target='docker_compose' requires docker='yes'.\n"
        "    The runbook would document a deployment whose Dockerfile was never generated."
    )


# --- Storage coherence -------------------------------------------------------

if STATIC_STORAGE == "cloud" and MEDIA_STORAGE == "filesystem":
    errors.append(
        "static_storage='cloud' requires a cloud media_storage.\n"
        "    Static files are served from the same object store as media, under a publicly\n"
        "    readable prefix. With media_storage='filesystem' there is no object store to put\n"
        "    them in. Either pick media_storage='s3'/'gcs'/'azure', or keep\n"
        "    static_storage='whitenoise'."
    )

if ASSET_PIPELINE == "compressor" and FRONTEND == "api_only":
    errors.append(
        "asset_pipeline='compressor' requires server-rendered templates.\n"
        "    Offline compression works by finding {% raw %}{% compress %}{% endraw %} blocks in templates, and an\n"
        "    API-only project has none - the build step would abort with\n"
        "    OfflineGenerationError. Set asset_pipeline='none'."
    )


# --- Background task queue ----------------------------------------------------
# task_broker and huey_backend are only read by the queue that owns them, and the
# unused one keeps its default value. That is deliberately not an error: nobody
# should have to answer a Celery question to generate a project with no queue.
# A NON-default broker is different - it is a choice that will silently not happen.

if TASK_BROKER in {"rabbitmq", "sqs"} and TASK_QUEUE != "celery":
    errors.append(
        f"task_broker='{TASK_BROKER}' requires task_queue='celery'.\n"
        "    Only Celery speaks to an external broker here. Huey is backed by PostgreSQL,\n"
        "    Redis or SQLite (see huey_backend) and cannot use AMQP or SQS, and\n"
        "    task_queue='none' has nothing to broker. Either set task_queue='celery', or\n"
        "    leave task_broker at its default."
    )


# --- Misc -------------------------------------------------------------------

if not re.match(r"^[a-z0-9.\-]+\.[a-z]{2,}$", DOMAIN_NAME):
    errors.append(
        f"domain_name {DOMAIN_NAME!r} does not look like a hostname. Provide it without a "
        "scheme or path, e.g. 'example.com'."
    )

if not re.match(r"^3\.\d{1,2}$", PYTHON_VERSION):
    errors.append(f"python_version {PYTHON_VERSION!r} should look like '3.13'.")


# --- Warnings (do not block generation) --------------------------------------

if TASK_QUEUE == "huey" and HUEY_BACKEND == "redis" and CACHE == "locmem":
    warnings.append(
        "task_queue='huey' with huey_backend='redis' but cache='locmem': nothing in this\n"
        "    project configures a real Redis, so HUEY_REDIS_URL falls back to a localhost\n"
        "    default that must exist on every machine that runs the worker. If you are not\n"
        "    already running Redis, huey_backend='postgres' needs no new service at all."
    )

if TASK_QUEUE == "huey" and HUEY_BACKEND == "sqlite":
    warnings.append(
        "huey_backend='sqlite': development and single-process use only. It does not\n"
        "    survive multiple workers, and a deployed site on SQLite contradicts the\n"
        "    PostgreSQL-only rule in the standards. Switch to 'postgres' before go-live."
    )

if TASK_QUEUE == "celery" and TASK_BROKER == "redis" and CACHE == "locmem":
    warnings.append(
        "task_queue='celery' with task_broker='redis' but cache='locmem': the broker needs\n"
        "    a real Redis server, and this project configures none - CELERY_BROKER_URL falls\n"
        "    back to a localhost default that must exist wherever the worker runs. Set\n"
        "    cache='redis' so one configured server serves both, or point CELERY_BROKER_URL\n"
        "    at a Redis you actually operate."
    )

if TASK_QUEUE == "celery" and TASK_BROKER == "sqs":
    warnings.append(
        "task_broker='sqs': celery[sqs] pulls in pycurl, which is a C extension built\n"
        "    against libcurl. 'uv sync' fails on a machine without libcurl and OpenSSL\n"
        "    headers, and the Docker builder stage installs them for exactly this reason.\n"
        "    Also: SQS carries no Celery remote control or events, so 'celery inspect' and\n"
        "    Flower's live monitoring do not work. See docs/06-installation.md."
    )

if SPAM_PROTECTION == "none":
    warnings.append(
        "spam_protection='none': public forms will have no bot protection.\n"
        "    This is a go-live finding under the security baseline and must be recorded as a\n"
        "    documented exception. Every public form is otherwise an open mail relay."
    )

if RATE_LIMITING == "no" and FRONTEND != "api_only":
    warnings.append(
        "rate_limiting='no': no login lockout and no limits on public POST endpoints.\n"
        "    The security baseline requires both. Record the exception."
    )

if USE_2FA == "no":
    warnings.append(
        "use_2fa='no': administrative accounts will not require two-factor authentication.\n"
        "    The security baseline requires 2FA for every admin account. Record the exception."
    )

if RATE_LIMITING == "yes" and CACHE == "locmem":
    warnings.append(
        "rate_limiting='yes' with cache='locmem': rate limit counters live in the Django\n"
        "    cache, and LocMemCache is per-process. With N gunicorn workers a '10/min' limit\n"
        "    becomes 10*N per minute. This is fine for development, but production must use\n"
        "    cache='redis'. The generated production settings will warn about this at boot."
    )

if API != "none" and CACHE == "locmem":
    warnings.append(
        "api != 'none' with cache='locmem': DRF throttle counters are also per-process.\n"
        "    Use cache='redis' in production."
    )

if ASSET_PIPELINE == "compressor":
    warnings.append(
        "asset_pipeline='compressor': COMPRESS_OFFLINE is on in production, so\n"
        "    'manage.py compress --force' MUST run on every deploy, after collectstatic.\n"
        "    It is wired into the Dockerfile and the deploy runbook; a deploy path that\n"
        "    skips it ships a site with no CSS. See docs/14-decisions.md for when this\n"
        "    option is worth its cost."
    )

if MEDIA_STORAGE != "filesystem":
    warnings.append(
        f"media_storage='{MEDIA_STORAGE}': the bucket must NOT be public-read. Personal\n"
        "    data goes to a separate private storage and is streamed through a\n"
        "    permission-checked view. 'backup' also changes meaning - see\n"
        "    docs/08-backup-restore.md before go-live."
    )

if NOTIFICATIONS == "no" and (FORMS_SUITE == "yes" or NEWSLETTER == "yes"):
    warnings.append(
        "notifications_app='no' with forms or newsletter enabled: transactional e-mail\n"
        "    templates will be hard-coded rather than editable in the admin, and there will be\n"
        "    no admin-visible e-mail log."
    )


# --- Report -----------------------------------------------------------------

if warnings:
    sys.stderr.write("\n")
    for warning in warnings:
        sys.stderr.write(f"WARNING: {warning}\n\n")

if errors:
    sys.stderr.write("\nProject generation aborted. Invalid option combination:\n\n")
    for error in errors:
        sys.stderr.write(f"  ERROR: {error}\n\n")
    sys.exit(1)
