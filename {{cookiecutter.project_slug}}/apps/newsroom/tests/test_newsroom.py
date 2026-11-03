"""The newsroom: articles are models, served by the one routable newsroom page."""

import pytest
from django.conf import settings
from django.urls import reverse
from django.utils import translation
from wagtail.models import Page

from apps.newsroom.models import NewsIndexPage

pytestmark = pytest.mark.django_db


def _get(client, url, **params):
    with translation.override(settings.LANGUAGE_CODE):
        return client.get(url, params)


def _article_url(newsroom, article):
    with translation.override(settings.LANGUAGE_CODE):
        return newsroom.url + newsroom.reverse_subpage("article", kwargs={"slug": article.slug})


def test_articles_are_never_pages(newsroom, make_article):
    """The rule this app exists to enforce: nothing in the page tree per article."""
    make_article("First", "first")

    assert NewsIndexPage.subpage_types == []
    assert not Page.objects.child_of(newsroom).exists()


def test_the_listing_shows_published_articles_newest_first(client, newsroom, make_article):
    make_article("Older", "older", days_ago=5)
    make_article("Newer", "newer", days_ago=1)

    response = _get(client, newsroom.url)

    assert response.status_code == 200
    assert [a.slug for a in response.context["articles"]] == ["newer", "older"]


def test_a_draft_is_neither_listed_nor_served(client, newsroom, make_article):
    draft = make_article("Draft", "draft", publish=False)

    assert draft.pk not in {a.pk for a in _get(client, newsroom.url).context["articles"]}
    assert _get(client, _article_url(newsroom, draft)).status_code == 404


def test_an_unpublished_article_stops_being_served(client, newsroom, make_article):
    article = make_article("Withdrawn", "withdrawn")
    url = _article_url(newsroom, article)
    assert _get(client, url).status_code == 200

    article.unpublish()

    assert _get(client, url).status_code == 404


def test_an_unknown_slug_is_a_404(client, newsroom):
    assert _get(client, newsroom.url + "no-such-article/").status_code == 404


def test_the_featured_article_leads_and_is_not_repeated(client, newsroom, make_article):
    make_article("Regular", "regular")
    featured = make_article("Featured", "featured", is_featured=True, days_ago=3)

    response = _get(client, newsroom.url)

    assert response.context["featured"] == featured
    assert featured.pk not in {a.pk for a in response.context["articles"]}


def test_the_category_filter_narrows_the_listing(client, newsroom, make_article, make_category):
    press = make_category("Press releases", "press-releases")
    make_article("Press", "press", category=press)
    make_article("Other", "other")

    response = _get(client, newsroom.url, category="press-releases")

    assert [a.slug for a in response.context["articles"]] == ["press"]
    assert response.context["featured"] is None


def test_an_unknown_category_is_ignored(client, newsroom, make_article):
    make_article("Any", "any")

    response = _get(client, newsroom.url, category="nonsense")

    assert response.status_code == 200
    assert response.context["current_category"] is None


def test_an_article_page_carries_its_own_seo(client, newsroom, make_article):
    article = make_article("A headline", "a-headline", search_description="Meta text.")

    content = _get(client, _article_url(newsroom, article)).content.decode()

    assert "A headline" in content
    assert 'content="Meta text."' in content
    assert 'property="og:type" content="article"' in content


def test_the_article_url_is_resolved_through_the_newsroom(newsroom, make_article):
    article = make_article("Addressed", "addressed")

    assert article.url == _article_url(newsroom, article)


def test_the_listing_query_count_does_not_scale_with_rows(
    client, newsroom, make_article, django_assert_max_num_queries
):
    """The performance standard's listing rule: no query per card."""
    for number in range(3):
        make_article(f"Few {number}", f"few-{number}")
    with django_assert_max_num_queries(60) as few:
        _get(client, newsroom.url)

    for number in range(9):
        make_article(f"Many {number}", f"many-{number}")
    with django_assert_max_num_queries(len(few.captured_queries)):
        _get(client, newsroom.url)


def test_published_articles_are_in_the_sitemap(client, make_article):
    make_article("Mapped", "mapped")
    make_article("Hidden", "hidden", publish=False)

    content = client.get("/sitemap.xml").content.decode()

    assert "/mapped/" in content
    assert "/hidden/" not in content


def test_published_articles_are_found_by_site_search(client, make_article):
    article = make_article("Quarterly results announced", "quarterly-results")

    with translation.override(settings.LANGUAGE_CODE):
        response = client.get(reverse("search:search"), {"q": "Quarterly"})

    assert article.url in [hit.url for hit in response.context["search_results"]]

{%- if cookiecutter.languages == "en_ar" %}


def test_switching_language_on_an_article_keeps_the_article(client, newsroom, make_article):
    """Regression: the switcher used to drop the routable sub-path."""
    article = make_article("Switchable", "switchable")

    content = _get(client, _article_url(newsroom, article)).content.decode()

    assert '/ar/news/switchable/"' in content
{%- endif %}
