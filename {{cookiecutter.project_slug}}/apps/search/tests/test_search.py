"""Search results, translated indexing and the public rate limit."""

import pytest
{%- if cookiecutter.rate_limiting == "yes" %}
from django.core.cache import cache
from django.test import override_settings
{%- endif %}
from django.urls import reverse
from wagtail.models import Page, Site
{%- if cookiecutter.languages == "en_ar" %}
from wagtail.search import index

from apps.home.models import HomePage
{%- endif %}

pytestmark = pytest.mark.django_db


def new_page(title, slug, **kwargs):
    """Build a page with every translated column filled in.

    The per-language columns are not optional - the default-language one is
    required - and the language active during a test is whatever the previous
    test left behind, so setting only the base ``title`` fails intermittently.
    """
    page = Page(title=title, slug=slug, **kwargs)
{%- if cookiecutter.languages == "en_ar" %}
    for code in ("en", "ar"):
        setattr(page, f"title_{code}", title)
        setattr(page, f"slug_{code}", slug)
{%- endif %}
    return page


@pytest.fixture
def site():
    return Site.objects.get(is_default_site=True)


@pytest.fixture
def article(site):
    """A published page inside the site's tree.

    Added under the seeded site root rather than by repointing the default Site:
    Wagtail caches site root paths in the Django cache, which is not rolled back
    with the test transaction, so repointing the site breaks URL resolution for
    every test that runs afterwards.
    """
    page = new_page("Zanzibar cable works", "zanzibar")
    site.root_page.add_child(instance=page)
    return page


def test_search_finds_a_published_page(client, article):
    response = client.get(reverse("search:search"), {"q": "Zanzibar"})

    assert response.status_code == 200
    assert "Zanzibar cable works" in response.content.decode()


def test_search_without_a_query_renders_the_empty_form(client, article):
    response = client.get(reverse("search:search"))

    assert response.status_code == 200
    assert response.context["result_count"] == 0


def test_results_pages_are_never_indexed(client, article):
    """An indexed results page competes with the pages it lists."""
    response = client.get(reverse("search:search"), {"q": "Zanzibar"})

    assert response.context["seo"]["noindex"] is True


def test_unpublished_pages_never_appear(client, article, site):
    draft = new_page("Zanzibar secret plans", "zanzibar-draft", live=False)
    site.root_page.add_child(instance=draft)

    response = client.get(reverse("search:search"), {"q": "Zanzibar"})

    assert "Zanzibar secret plans" not in response.content.decode()
{%- if cookiecutter.languages == "en_ar" %}


def test_translated_columns_are_indexed():
    """Arabic search must match Arabic content.

    Without the registration in apps.search.indexing the query runs against the
    English columns and quietly returns nothing, which reaches us as "search does
    not work in Arabic" months after launch.
    """
    indexed_names = {field.field_name for field in HomePage.search_fields}

    assert "title_ar" in indexed_names
    assert "introduction_ar" in indexed_names


def test_registration_is_idempotent():
    from apps.search.indexing import register_translated_search_fields

    before = len(HomePage.search_fields)
    register_translated_search_fields()

    assert len(HomePage.search_fields) == before


def test_only_full_text_fields_are_duplicated():
    """Filter fields must not be cloned: they are not searchable columns."""
    for field in HomePage.search_fields:
        if field.field_name.endswith("_ar"):
            assert isinstance(field, index.SearchField | index.AutocompleteField)


def test_arabic_query_matches_arabic_content(client, article):
    article.title_ar = "مصنع الكابلات"
    article.save()

    response = client.get(reverse("search:search"), {"q": "الكابلات"})

    assert response.status_code == 200
    assert response.context["result_count"] == 1
{%- endif %}
{%- if cookiecutter.rate_limiting == "yes" %}


@override_settings(RATELIMIT_ENABLE=True, RATELIMIT_SEARCH="2/m")
def test_search_is_rate_limited(client, article):
    """Search is a public endpoint that costs a full-text query per request."""
    cache.clear()
    url = reverse("search:search")

    for _attempt in range(2):
        assert client.get(url, {"q": "Zanzibar"}).status_code == 200

    blocked = client.get(url, {"q": "Zanzibar"})

    assert blocked.status_code == 429
    assert blocked.context["rate_limited"] is True
{%- endif %}
