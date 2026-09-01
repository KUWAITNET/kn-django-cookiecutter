"""Template context shared by every rendered page.

HTML templates are copied out of the generator verbatim, so nothing in them can
depend on a cookiecutter variable. Anything that differs per project therefore
arrives here, from settings.
"""

from django.conf import settings

from apps.core.utils import language_alternatives, static_absolute_url

#: Sharing image used when a page supplies none. Resolved in Python, never with
#: ``{% raw %}{% static %}{% endraw %}``: under a hashed manifest a missing file raises, and a raise
#: inside the shared head partial is a 500 on every page of the site.
DEFAULT_OG_IMAGE_STATIC_PATH = "img/og-default.jpg"


def site_context(request):
    """Project identity, SEO defaults, analytics IDs and form-protection flags."""
    return {
        "SITE_NAME": settings.SITE_NAME,
        "SITE_DESCRIPTION": getattr(settings, "SITE_DESCRIPTION", ""),
        "CLIENT_NAME": settings.CLIENT_NAME,
        "BASE_URL": settings.BASE_URL,
        "DEFAULT_OG_IMAGE_URL": static_absolute_url(DEFAULT_OG_IMAGE_STATIC_PATH),
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
    }
