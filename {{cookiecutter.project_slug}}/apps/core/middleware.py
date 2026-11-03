"""Request/response middleware for {{ cookiecutter.project_name }}."""

from django.conf import settings
from django.middleware.locale import LocaleMiddleware


class NonLocalisedPathLocaleMiddleware(LocaleMiddleware):
    """LocaleMiddleware that leaves non-localised paths alone.

    Django's LocaleMiddleware turns a 404 on an unprefixed path into a 302 to the
    language-prefixed equivalent, so that a visitor typing ``/about/`` lands on
    ``/en/about/``. That is right for pages and wrong for everything else: an API
    client asking for an object that does not exist must receive 404 with the
    problem+json body, not a redirect to ``/en/api/v1/...`` that it will either
    follow into another 404 or treat as success.

    The same applies to any machine-readable endpoint mounted outside
    ``i18n_patterns`` - the health check, ``robots.txt``, ``sitemap.xml`` and
    permission-checked media downloads.

    Paths listed in ``settings.LOCALE_REDIRECT_EXEMPT_PREFIXES`` keep whatever
    status their view returned.
    """

    def process_response(self, request, response):
        exempt = tuple(getattr(settings, "LOCALE_REDIRECT_EXEMPT_PREFIXES", ()))
        if exempt and request.path_info.startswith(exempt):
            return response
        return super().process_response(request, response)
