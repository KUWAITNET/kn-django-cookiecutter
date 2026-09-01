"""Deployment system checks.

``manage.py check --deploy`` covers Django's own settings. These cover the ones
this template adds, and they fire under the production settings module so a
misconfiguration is caught by CI or the deploy step rather than at go-live.

They are warnings, not errors: a warning is loud enough to be seen and does not
stop an emergency deploy. Anything that must be impossible is enforced in
settings, not here.
{%- if cookiecutter.media_storage != "filesystem" %}

The one exception is a media bucket configured to be world-readable. That is an
ERROR, so ``manage.py check`` exits non-zero and the deploy stops: it publishes
every CV and ID copy the site has ever received, and no deploy is urgent enough
to be worth that.
{%- endif %}
"""

import os

from django.conf import settings
{%- if cookiecutter.media_storage == "filesystem" %}
from django.core.checks import Tags, Warning, register
{%- else %}
from django.core.checks import Error, Tags, Warning, register
{%- endif %}

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
