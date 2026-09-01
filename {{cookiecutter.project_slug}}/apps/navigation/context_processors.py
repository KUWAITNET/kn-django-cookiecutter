{%- if cookiecutter.multisite == "multi" -%}
"""Cross-site context for the header's site switcher.

Only registered on multi-site projects. Everything here comes from the Wagtail
``Site`` table rather than from sniffing the Host header: the reference project
decided which country it was serving by testing for the substring "jordan" in the
host, which nobody could extend without a deployment and which mislabelled every
staging domain.
"""
{% if cookiecutter.languages == "en_ar" %}
from django.conf import settings
from django.utils.translation import get_language
{%- endif %}
from wagtail.models import Site


def site_switcher(request):
    """The sites this installation serves, flagged with the current one."""
    if request is None:
        return {}

    try:
        current_site = Site.find_for_request(request)
    except Site.DoesNotExist:
        current_site = None
{%- if cookiecutter.languages == "en_ar" %}

    # Every public URL carries an explicit language prefix. A bare root URL would
    # be resolved by the other site's language negotiation instead, which silently
    # drops an Arabic visitor into English.
    language_code = get_language() or settings.LANGUAGE_CODE
{%- endif %}

    available_sites = []
    for site in Site.objects.select_related("root_page").order_by("hostname"):
{%- if cookiecutter.languages == "en_ar" %}
        url = f"{site.root_url.rstrip('/')}/{language_code}/"
{%- else %}
        url = f"{site.root_url.rstrip('/')}/"
{%- endif %}
        available_sites.append(
            {
                "site": site,
                "label": site.site_name or site.hostname,
                "url": url,
                "is_current": current_site is not None and site.pk == current_site.pk,
            }
        )

    return {"current_site": current_site, "available_sites": available_sites}
{%- endif %}
