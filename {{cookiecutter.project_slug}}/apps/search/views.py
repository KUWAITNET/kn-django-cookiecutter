"""Site search over the published page tree."""

{% if cookiecutter.rate_limiting == "yes" %}from django.conf import settings
{% endif %}from django.core.paginator import Paginator
from django.shortcuts import render
from django.utils.translation import gettext as _
{%- if cookiecutter.rate_limiting == "yes" %}
from django_ratelimit.decorators import ratelimit
{%- endif %}
{%- if cookiecutter.multisite == "multi" %}
from wagtail.models import Page, Site
{%- else %}
from wagtail.models import Page
{%- endif %}

RESULTS_PER_PAGE = 10


def _seo_context():
    """SEO overrides read by the shared head partial.

    A results page must be noindex: an indexed one competes with the pages it
    lists and lets anyone mint arbitrary indexed URLs from the query string.
    """
    return {"base_title": _("Search"), "noindex": True}
{% if cookiecutter.rate_limiting == "yes" %}

def _search_rate(group, request):
    """Read the budget per request rather than baking it in at import time.

    Keeps the limit configurable from settings and lets the tests exercise it
    without restarting anything.
    """
    return settings.RATELIMIT_SEARCH


@ratelimit(key="ip", rate=_search_rate, method="GET", block=False)
def search(request):
{%- else %}

def search(request):
{%- endif %}
    """Render search results for the ``q`` query parameter.

    Only live, public pages are searched, so an unpublished or privacy-protected
    page can never leak its title through the results list.
    """
    query = (request.GET.get("q") or "").strip()
{%- if cookiecutter.rate_limiting == "yes" %}

    # Every search costs a full-text query. Rendering a 429 page instead of
    # raising keeps the message translated and the layout intact.
    if getattr(request, "limited", False):
        return render(
            request,
            "search/search.html",
            {"search_query": query, "rate_limited": True, "seo": _seo_context()},
            status=429,
        )
{%- endif %}

    pages = Page.objects.live().public()
{%- if cookiecutter.multisite == "multi" %}
    # Restrict to this site's own tree: the sites share a database, and an
    # unscoped search shows visitors pages belonging to the other site.
    try:
        site = Site.find_for_request(request)
    except Site.DoesNotExist:
        site = None
    if site is not None:
        pages = pages.descendant_of(site.root_page)
{%- endif %}

    results = pages.search(query) if query else Page.objects.none()

    paginator = Paginator(results, RESULTS_PER_PAGE)
    results_page = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "search/search.html",
        {
            "search_query": query,
            "search_results": results_page,
            "result_count": paginator.count if query else 0,
            "seo": _seo_context(),
        },
    )
