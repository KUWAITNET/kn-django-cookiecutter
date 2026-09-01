"""Deployment system checks.

``manage.py check --deploy`` covers Django's own settings. These cover the ones
this template adds, and they fire under the production settings module so a
misconfiguration is caught by CI or the deploy step rather than at go-live.

They are warnings, not errors: a warning is loud enough to be seen and does not
stop an emergency deploy. Anything that must be impossible is enforced in
settings, not here.
"""

import os

from django.conf import settings
from django.core.checks import Tags, Warning, register

#: Values that mean "nobody set a real key".
PLACEHOLDER_SECRET_KEY_PREFIXES = ("django-insecure", "change-me", "changeme", "secret")


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
