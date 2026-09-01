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


# --- Admin URL prefix -------------------------------------------------------

if not ADMIN_URL_PREFIX:
    errors.append("admin_url_prefix must not be empty.")
elif ADMIN_URL_PREFIX.strip("/") == "admin":
    errors.append(
        "admin_url_prefix must not be 'admin'.\n"
        "    The default admin path is the first thing automated scanners try. Choose a\n"
        "    project-specific prefix (see the security baseline, 'Administrative surface').\n"
        "    Note this is defence in depth, not a security control in its own right."
    )
elif not re.match(r"^[a-z0-9][a-z0-9\-_]*$", ADMIN_URL_PREFIX):
    errors.append(
        f"admin_url_prefix {ADMIN_URL_PREFIX!r} must be URL-safe: lowercase letters, "
        "digits, hyphens and underscores only, with no leading or trailing slash."
    )
elif ADMIN_URL_PREFIX in {"api", "static", "media", "search", "accounts", "documents", "images"}:
    errors.append(
        f"admin_url_prefix {ADMIN_URL_PREFIX!r} collides with another URL prefix used by "
        "the project."
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


# --- Misc -------------------------------------------------------------------

if not re.match(r"^[a-z0-9.\-]+\.[a-z]{2,}$", DOMAIN_NAME):
    errors.append(
        f"domain_name {DOMAIN_NAME!r} does not look like a hostname. Provide it without a "
        "scheme or path, e.g. 'example.com'."
    )

if not re.match(r"^3\.\d{1,2}$", PYTHON_VERSION):
    errors.append(f"python_version {PYTHON_VERSION!r} should look like '3.13'.")


# --- Warnings (do not block generation) --------------------------------------

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
