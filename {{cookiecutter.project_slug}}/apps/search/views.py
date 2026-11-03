"""Site search over the published page tree{% if cookiecutter.newsroom == "yes" %} and the published newsroom articles{% endif %}."""

{% if cookiecutter.newsroom == "yes" %}from dataclasses import dataclass

from django.apps import apps
{% endif %}{% if cookiecutter.rate_limiting == "yes" %}from django.conf import settings
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
{%- if cookiecutter.newsroom == "yes" %}

#: Per source. A search that needs more than this many hits to find its answer
#: needs a better query, and the cap keeps one request from materialising the
#: whole index.
MAX_HITS_PER_SOURCE = 100


@dataclass(frozen=True)
class SearchHit:
    """One result, whatever it came from - a page or a newsroom article."""

    title: str
    url: str
    description: str


def _page_hits(pages, query):
    return [
        SearchHit(str(page.title), page.url or "", page.search_description or "")
        for page in pages.specific().search(query)[:MAX_HITS_PER_SOURCE]
    ]


def _article_hits(request, query):
    """Published articles. They are models, not pages, so the page search never sees them.

    Links are built from the newsroom page looked up once, not per article.
    """
    NewsArticle = apps.get_model("newsroom", "NewsArticle")
    newsroom = apps.get_model("newsroom", "NewsIndexPage").for_request(request)
    base = newsroom.url if newsroom is not None else ""
    if not base:
        return []
    return [
        SearchHit(
            article.title,
            base + newsroom.reverse_subpage("article", kwargs={"slug": article.slug}),
            article.search_description or article.introduction,
        )
        for article in NewsArticle.objects.published().search(query)[:MAX_HITS_PER_SOURCE]
    ]
{%- endif %}


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

    Only live, public pages{% if cookiecutter.newsroom == "yes" %} and published articles{% endif %} are searched, so an
    unpublished or privacy-protected item can never leak its title through the
    results list.
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

{%- if cookiecutter.newsroom == "yes" %}
    results = [*_page_hits(pages, query), *_article_hits(request, query)] if query else []
{%- else %}
    results = pages.search(query) if query else Page.objects.none()
{%- endif %}

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
