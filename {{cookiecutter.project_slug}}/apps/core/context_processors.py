"""Template context shared by every rendered page.

HTML templates are copied out of the generator verbatim, so nothing in them can
depend on a cookiecutter variable. Anything that differs per project therefore
arrives here, from settings.
"""

from django.apps import apps as django_apps
from django.conf import settings
{%- if cookiecutter.stack == "django" %}
from django.db import DatabaseError
{%- endif %}

{% if cookiecutter.stack == "django" -%}
from apps.core.models import SiteConfiguration
{% endif -%}
from apps.core.utils import language_alternatives, static_absolute_url

#: Sharing image used when a page supplies none. Resolved in Python, never with
#: ``{% raw %}{% static %}{% endraw %}``: under a hashed manifest a missing file raises, and a raise
#: inside the shared head partial is a 500 on every page of the site.
DEFAULT_OG_IMAGE_STATIC_PATH = "img/og-default.jpg"
{%- if cookiecutter.stack == "django" %}


def site_configuration():
    """The configuration singleton, or ``None`` when the database cannot answer.

    Guarded because the 500 page renders through this same context processor: an
    unguarded query here would turn a database outage into a second exception
    raised while reporting the first, and the visitor would get a bare stack
    trace instead of the branded error page. Falling back to settings is always
    safe - every value this row carries has a deployed default behind it.
    """
    try:
        return SiteConfiguration.get_solo()
    except DatabaseError:
        return None
{%- endif %}


def site_context(request):
    """Project identity, SEO defaults, analytics IDs and form-protection flags."""
{%- if cookiecutter.stack == "django" %}
    # Anything an administrator has filled in wins over the deployed default; a
    # blank field means "use the deployed default", never "render nothing". That
    # is what lets a template read one variable name and stop caring which of the
    # two supplied it.
    configuration = site_configuration()
    site_name = (configuration.site_name if configuration else "") or settings.SITE_NAME
    og_image_url = (configuration.share_image_url if configuration else "") or static_absolute_url(
        DEFAULT_OG_IMAGE_STATIC_PATH
    )
{%- endif %}
    return {
{%- if cookiecutter.stack == "django" %}
        "SITE_NAME": site_name,
{%- else %}
        "SITE_NAME": settings.SITE_NAME,
{%- endif %}
        "SITE_DESCRIPTION": getattr(settings, "SITE_DESCRIPTION", ""),
        "CLIENT_NAME": settings.CLIENT_NAME,
        "BASE_URL": settings.BASE_URL,
{%- if cookiecutter.stack == "django" %}
        # The whole singleton, for the logo, contact details and social links.
        # ``None`` only when the database is unreachable, and every template that
        # reads it must tolerate that - {% raw %}{% if SITE_CONFIG.logo %}{% endraw %} does.
        "SITE_CONFIG": configuration,
        "DEFAULT_OG_IMAGE_URL": og_image_url,
{%- else %}
        "DEFAULT_OG_IMAGE_URL": static_absolute_url(DEFAULT_OG_IMAGE_STATIC_PATH),
{%- endif %}
        # Search-console / webmaster verification tokens, as a list so several
        # can coexist without a template change.
        "SEO_SITE_VERIFICATION": getattr(settings, "SEO_SITE_VERIFICATION", []),
        "GA4_MEASUREMENT_ID": settings.GA4_MEASUREMENT_ID,
        "GTM_CONTAINER_ID": settings.GTM_CONTAINER_ID,
        "SPAM_PROTECTION": settings.SPAM_PROTECTION,
{%- if cookiecutter.spam_protection == "turnstile_honeypot" %}
        # Empty when no key is configured; the form templates use that to fall
        # back to honeypot-only so development, CI and UAT are never blocked.
        "TURNSTILE_SITE_KEY": settings.TURNSTILE_SITE_KEY,
{%- endif %}
        # One entry per language: code, name, name_local, bidi, is_current and the
        # absolute URL of *this* page in that language (translated slug, query
        # string preserved, empty when there is no version in that language).
        # Drives hreflang, x-default, og:locale and the language switcher, which
        # is why they all read the same list instead of each deriving their own.
        "LANGUAGES_AVAILABLE": language_alternatives(request),
        # Checked at runtime rather than generation time so a template can guard
        # an {% raw %}{% include %}{% endraw %} of an optional app without failing to compile when that
        # app is absent.
        "NEWSLETTER_ENABLED": django_apps.is_installed("apps.newsletter"),
    }
