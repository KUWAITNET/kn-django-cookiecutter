"""Deployment system checks.

``manage.py check --deploy`` covers Django's own settings. These cover the ones
this template adds, and they fire under the production settings module so a
misconfiguration is caught by CI or the deploy step rather than at go-live.

Severity follows the standard's own language. A rule the security baseline states
as a **must** is an ``Error``, so ``manage.py check`` exits non-zero and the
deploy stops. A rule it states as a **should**, and anything this file can only
infer, is a ``Warning``: loud enough to be seen in CI, and not something that
blocks an emergency deploy at 2am.

Which rule is enforced where - here, in CI, in a lint rule, in
``tools/check_standards.py``, or only by somebody signing a checklist - is
tabulated in ``docs/enforcement.md`` in the KUWAITNET web standards repository.
"""

import os

from django.conf import settings
from django.core.checks import Error, Tags, Warning, register

#: Values that mean "nobody set a real key".
PLACEHOLDER_SECRET_KEY_PREFIXES = ("django-insecure", "change-me", "changeme", "secret")
{%- if cookiecutter.media_storage != "filesystem" %}

#: ACL values that publish an object to the entire internet.
WORLD_READABLE_ACLS = frozenset(
    {"public-read", "public-read-write", "publicRead", "publicReadWrite"}
)

#: The storage aliases that can end up holding personal data.
MEDIA_STORAGE_ALIASES = ("default", "private_media")
{%- endif %}


def _is_production_settings() -> bool:
    """True when the process is running the production settings module."""
    module = os.environ.get("DJANGO_SETTINGS_MODULE", "")
    return module.rsplit(".", 1)[-1] == "production"


@register(Tags.security)
def check_debug_is_off(app_configs, **kwargs):
    if not _is_production_settings() or not settings.DEBUG:
        return []
    return [
        Warning(
            "DEBUG is on under the production settings module.",
            hint=(
                "Every traceback, every setting name and the SQL log become public. "
                "Unset DEBUG in the environment."
            ),
            id="core.W001",
        )
    ]


@register(Tags.security)
def check_secret_key(app_configs, **kwargs):
    if not _is_production_settings():
        return []
    key = settings.SECRET_KEY or ""
    if len(key) >= 50 and not key.lower().startswith(PLACEHOLDER_SECRET_KEY_PREFIXES):
        return []
    return [
        Warning(
            "SECRET_KEY looks like a development placeholder.",
            hint=(
                "Session cookies, password-reset links and signed values are all "
                "forgeable with a known key. Set SECRET_KEY in the environment to a "
                "random value of at least 50 characters."
            ),
            id="core.W002",
        )
    ]


@register(Tags.security)
def check_allowed_hosts(app_configs, **kwargs):
    """A wildcard host is what makes Host-header poisoning work."""
    if not _is_production_settings() or "*" not in settings.ALLOWED_HOSTS:
        return []
    return [
        Error(
            "ALLOWED_HOSTS accepts any Host header under the production settings.",
            hint=(
                "Django then trusts whatever a request claims the site is called, so a "
                "password-reset link can be built pointing at an attacker's domain and "
                "cache keys can be poisoned. Set ALLOWED_HOSTS in the environment to the "
                "real hostnames, and nothing else."
            ),
            id="core.E003",
        )
    ]


@register(Tags.security)
def check_admin_url_prefix(app_configs, **kwargs):
    """Not gated on production: the prefix is the same value in every environment."""
    if settings.ADMIN_URL_PREFIX.strip("/") != "admin":
        return []
    return [
        Error(
            "The admin is mounted at /admin/.",
            hint=(
                "It is the first path every automated scanner tries, so the login form - "
                "and the account lockout behind it - is found by everyone. Set "
                "ADMIN_URL_PREFIX to a project-specific value and update the deploy "
                "documentation. This is defence in depth, not a substitute for 2FA."
            ),
            id="core.E004",
        )
    ]


@register(Tags.security)
def check_script_src_is_strict(app_configs, **kwargs):
    """A nonce-based CSP that also allows inline script protects nothing.

    Not gated on production: the policy is defined once, in base settings, and a
    developer loosening it locally is exactly the change that then ships.
    """
    policy = getattr(settings, "CONTENT_SECURITY_POLICY", {}) or {}
    directives = policy.get("DIRECTIVES", {})
    sources = directives.get("script-src") or directives.get("default-src") or []
    found = [
        source
        for source in sources
        if isinstance(source, str) and source in ("'unsafe-inline'", "'unsafe-eval'")
    ]
    if not found:
        return []
    return [
        Error(
            f"CONTENT_SECURITY_POLICY script-src allows {', '.join(found)}.",
            hint=(
                "The browser stops distinguishing our script from injected script, which "
                "is the one thing the policy exists to do - and the nonce becomes "
                "decoration. Move the inline code into a static file, or give the tag "
                "nonce=\"{% raw %}{{ request.csp_nonce }}{% endraw %}\". If a vendored "
                "library needs eval, replace the library."
            ),
            id="core.E005",
        )
    ]


@register(Tags.security)
def check_audit_log_retention(app_configs, **kwargs):
    """Twelve months is the standard, and an audit log is only useful in hindsight.

    An unset AUDITLOG_RETENTION_DAYS is not a finding: it means this project has
    no prune job at all, so nothing deletes an entry. Too short a retention is
    the failure mode worth catching, because it looks configured.
    """
    days = getattr(settings, "AUDITLOG_RETENTION_DAYS", None)
    if days is None or days >= 365:
        return []
    return [
        Error(
            f"AUDITLOG_RETENTION_DAYS is {days}, below the 365-day minimum.",
            hint=(
                "Administrative changes are usually questioned months later - who changed "
                "this price, who deleted this page, which account was used. A log pruned "
                "before then answers nothing. Raise AUDITLOG_RETENTION_DAYS to at least "
                "365; if storage is the concern, that is a conversation about archiving, "
                "not about retention."
            ),
            id="core.E006",
        )
    ]
{%- if cookiecutter.use_2fa == "yes" %}


@register(Tags.security)
def check_two_factor_is_enforced(app_configs, **kwargs):
    """The second factor can be switched off by an environment variable."""
{%- if cookiecutter.stack == "wagtail" %}
    required = getattr(settings, "WAGTAIL_2FA_REQUIRED", False)
{%- else %}
    required = getattr(settings, "OTP_ADMIN_REQUIRED", False)
{%- endif %}
    if not _is_production_settings() or required:
        return []
    return [
        Error(
            "Two-factor authentication is installed but not required.",
            hint=(
                "A stolen or reused password is then a working administrative session, "
                "and every admin view - accounts, content, the e-mail log, uploaded "
                "files - is reachable from it. Unset the environment variable that "
                "disabled it; the test settings are the only place it may be off."
            ),
            id="core.E007",
        )
    ]
{%- else %}


@register(Tags.security)
def check_two_factor_exception_is_visible(app_configs, **kwargs):
    """This project was generated without 2FA, which is a documented exception.

    It stays a warning rather than an error because it was chosen deliberately.
    It is emitted on every production check anyway, because an exception nobody
    is reminded of is indistinguishable from an oversight - and this one has to
    be defended at the go-live security pass by whoever signs it.
    """
    if not _is_production_settings():
        return []
    return [
        Warning(
            "Administrative accounts have no second factor.",
            hint=(
                "The KUWAITNET standard is 2FA on every administrative account; this "
                "project was generated with use_2fa=no. Record the exception and its "
                "reason in docs/14-decisions.md, and expect it as a finding on the "
                "go-live checklist. Adding django-otp later is a smaller job than "
                "explaining a compromised admin account."
            ),
            id="core.W007",
        )
    ]
{%- endif %}
{%- if cookiecutter.frontend != "api_only" %}


@register(Tags.security)
def check_spam_protection(app_configs, **kwargs):
    """A public form with no bot protection fills the inbox and the database."""
    if not _is_production_settings() or settings.SPAM_PROTECTION != "none":
        return []
    return [
        Warning(
            "Public forms have no spam or bot protection under the production settings.",
            hint=(
                "Every public form becomes a mail relay and an unbounded write path, and "
                "it is discovered by scanners within days of go-live. The standard is "
                "Turnstile with a honeypot behind it. If this was a deliberate choice, "
                "record it in docs/14-decisions.md - it is a go-live finding either way."
            ),
            id="core.W008",
        )
    ]
{%- endif %}
{%- if cookiecutter.rate_limiting != "yes" %}


@register(Tags.security)
def check_rate_limiting_exception_is_visible(app_configs, **kwargs):
    """Generated with rate limiting off, which is a documented exception."""
    if not _is_production_settings():
        return []
    return [
        Warning(
            "There is no rate limiting and no login lockout.",
            hint=(
                "Credential stuffing against the admin login, and automated submission of "
                "every public form, both run until something else stops them. The "
                "standard is django-axes on authentication and django-ratelimit on public "
                "POST endpoints. Record the exception in docs/14-decisions.md."
            ),
            id="core.W009",
        )
    ]
{%- else %}


@register(Tags.security)
def check_rate_limiting_is_enabled(app_configs, **kwargs):
    """RATELIMIT_ENABLE and AXES_ENABLED are both one environment variable away."""
    if not _is_production_settings():
        return []
    disabled = [
        name
        for name, value in (
            ("RATELIMIT_ENABLE", getattr(settings, "RATELIMIT_ENABLE", True)),
            ("AXES_ENABLED", getattr(settings, "AXES_ENABLED", True)),
        )
        if not value
    ]
    if not disabled:
        return []
    return [
        Warning(
            f"Rate limiting is installed but switched off ({', '.join(disabled)}).",
            hint=(
                "The decorators still run and do nothing, so the protection reads as "
                "present in code review and is absent in production. It is off in the "
                "test settings on purpose; nowhere else."
            ),
            id="core.W010",
        )
    ]
{%- endif %}
{%- if cookiecutter.rate_limiting == "yes" %}


@register(Tags.caches)
def check_rate_limit_cache(app_configs, **kwargs):
    if not _is_production_settings():
        return []
    backend = settings.CACHES.get("default", {}).get("BACKEND", "")
    if "locmem" not in backend and "dummy" not in backend:
        return []
    return [
        Warning(
            "Rate limiting is enabled but the default cache is per process.",
            hint=(
                "Each gunicorn worker keeps its own counters, so a '5/h' limit "
                "becomes 5/h per worker. Point CACHES['default'] at Redis."
            ),
            id="core.W003",
        )
    ]
{%- endif %}
{%- if cookiecutter.spam_protection == "turnstile_honeypot" %}


@register(Tags.security)
def check_turnstile_key(app_configs, **kwargs):
    if not _is_production_settings() or settings.TURNSTILE_SECRET_KEY:
        return []
    return [
        Warning(
            "Spam protection is enabled but no Turnstile secret key is configured.",
            hint=(
                "Protection has degraded to honeypot-only, which stops naive bots "
                "and nothing else. Set TURNSTILE_SITE_KEY and TURNSTILE_SECRET_KEY."
            ),
            id="core.W004",
        )
    ]
{%- endif %}


{%- if cookiecutter.media_storage != "filesystem" %}


def _storage_options(alias):
    return settings.STORAGES.get(alias, {}).get("OPTIONS", {})


@register(Tags.security)
def check_media_bucket_is_not_world_readable(app_configs, **kwargs):
    """No media storage may publish what it stores.

    Not gated on the production settings module: a public ACL is wrong in every
    environment, and a UAT bucket full of real client data is the same leak as a
    production one.
    """
    problems = []
    for alias in MEDIA_STORAGE_ALIASES:
        options = _storage_options(alias)
        acl = options.get("default_acl")
        if acl in WORLD_READABLE_ACLS:
            problems.append(
                Error(
                    f"STORAGES['{alias}'] sends a world-readable ACL ({acl!r}).",
                    hint=(
                        "Every object it stores becomes a public document the moment "
                        "its key is guessed or logged - which is how applicant CVs "
                        "leaked in the reference project. Set 'default_acl' to None "
                        "and grant read access through a bucket policy scoped to the "
                        "static prefix only."
                    ),
                    id="core.E001",
                )
            )
{%- if cookiecutter.media_storage == "azure" %}
    # Azure has no per-object ACL: an unsigned URL is only usable when the whole
    # container was opened for anonymous blob read, so that is the tell.
    if _storage_options("private_media").get("expiration_secs", "unset") is None:
        problems.append(
            Error(
                "STORAGES['private_media'] builds unsigned blob URLs.",
                hint=(
                    "An unsigned Azure blob URL only resolves when the container "
                    "allows anonymous read, which would publish every private "
                    "upload. Set 'expiration_secs' so each URL is a short-lived SAS."
                ),
                id="core.E002",
            )
        )
{%- else %}
    if _storage_options("private_media").get("querystring_auth") is False:
        problems.append(
            Error(
                "STORAGES['private_media'] builds unsigned URLs.",
                hint=(
                    "An unsigned object URL only resolves when the bucket allows "
                    "anonymous read, which would publish every private upload. Set "
                    "'querystring_auth' to True so each URL is signed and expires."
                ),
                id="core.E002",
            )
        )
{%- endif %}
    return problems


@register(Tags.files)
def check_cloud_media_credentials(app_configs, **kwargs):
    """Media is in a bucket, so a missing name or key means every upload fails.

    It fails at upload time, in front of a visitor, rather than at boot - which is
    why this is worth a check rather than a stack trace in Sentry three days later.
    """
    if not _is_production_settings():
        return []

    missing = []
{%- if cookiecutter.media_storage == "s3" %}
    if not settings.AWS_STORAGE_BUCKET_NAME:
        missing.append("AWS_STORAGE_BUCKET_NAME")
    if not settings.AWS_S3_REGION_NAME and not settings.AWS_S3_ENDPOINT_URL:
        missing.append("AWS_S3_REGION_NAME (or AWS_S3_ENDPOINT_URL for a compatible store)")
    # An instance role or IRSA is the preferred credential and leaves both of
    # these unset, so only half a key pair is reported - that is always a mistake.
    if bool(settings.AWS_ACCESS_KEY_ID) != bool(settings.AWS_SECRET_ACCESS_KEY):
        missing.append("AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY (only one is set)")
{%- elif cookiecutter.media_storage == "gcs" %}
    if not settings.GS_BUCKET_NAME:
        missing.append("GS_BUCKET_NAME")
    # Workload identity and the metadata server are the preferred credentials and
    # leave this unset, so this is a hint rather than a certainty - hence a warning.
    if not settings.GOOGLE_APPLICATION_CREDENTIALS:
        missing.append("GOOGLE_APPLICATION_CREDENTIALS (unless workload identity is in use)")
{%- if cookiecutter.static_storage == "cloud" %}
    # GCS IAM is per bucket and uniform access disables object ACLs, so "public
    # static, private media" is not expressible inside one bucket. Sharing it means
    # either the CSS is unreachable or every upload is public - never what was meant.
    if settings.GS_STATIC_BUCKET_NAME == settings.GS_BUCKET_NAME:
        missing.append("GS_STATIC_BUCKET_NAME (public static files need a bucket of their own)")
{%- endif %}
{%- else %}
    if not settings.AZURE_CONTAINER:
        missing.append("AZURE_CONTAINER")
    if not settings.AZURE_CONNECTION_STRING and not settings.AZURE_ACCOUNT_NAME:
        missing.append("AZURE_ACCOUNT_NAME or AZURE_CONNECTION_STRING")
    if (
        settings.AZURE_ACCOUNT_NAME
        and not settings.AZURE_ACCOUNT_KEY
        and not settings.AZURE_CONNECTION_STRING
    ):
        missing.append("AZURE_ACCOUNT_KEY (unless a managed identity is in use)")
{%- if cookiecutter.static_storage == "cloud" %}
    # Public access is a per-container setting in Azure with no per-object override,
    # so "public static, private media" is not expressible inside one container.
    # Sharing it means either the CSS is unreachable or every upload is public.
    if settings.AZURE_STATIC_CONTAINER == settings.AZURE_CONTAINER:
        missing.append("AZURE_STATIC_CONTAINER (public static files need a container of their own)")
{%- endif %}
{%- endif %}
    if not missing:
        return []
    return [
        Warning(
            "Media is stored in the cloud but the configuration is incomplete: "
            + ", ".join(missing)
            + ".",
            hint=(
                "Uploads will fail in front of a visitor rather than at boot. Set "
                "these in the environment; see docs/04-environment-variables.md."
            ),
            id="core.W006",
        )
    ]
{%- endif %}


@register(Tags.files)
def check_content_sniffing_available(app_configs, **kwargs):
    """libmagic is a system package, so it goes missing on a new host quietly."""
    from apps.core.validators import content_sniffing_available

    if content_sniffing_available():
        return []
    return [
        Warning(
            "libmagic is unavailable, so upload content sniffing cannot run.",
            hint=(
                "Every upload will be refused until it is installed "
                "(Debian/Ubuntu: libmagic1, macOS: brew install libmagic)."
            ),
            id="core.W005",
        )
    ]
