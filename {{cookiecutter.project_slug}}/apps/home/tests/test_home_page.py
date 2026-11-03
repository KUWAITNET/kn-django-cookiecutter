"""The home page serves, in every configured language."""

import pytest
from django.conf import settings
from django.utils import translation
from wagtail.models import Page, Site

from apps.home.models import HomePage

pytestmark = pytest.mark.django_db


@pytest.fixture
def home_page():
    """The site's own home page, as ``seed_content`` created it.

    Deliberately does NOT create a page and repoint the default Site at it.
    Wagtail caches site root paths in the Django cache, which is not rolled back
    with the test transaction, so a fixture that repoints the site leaves every
    later test resolving URLs against a page that no longer exists - and
    ``page.url`` then quietly returns None rather than raising.
    """
    site = Site.objects.get(is_default_site=True)
    page = HomePage.objects.filter(pk=site.root_page_id).first()
    assert page is not None, "seed_content must create the home page (see conftest.py)"
    return page
{% if cookiecutter.languages == "en_ar" %}

@pytest.mark.parametrize("language_code", ["en", "ar"])
def test_home_page_serves_in_each_language(client, home_page, language_code):
    """Both prefixes must serve.

    With prefix_default_language=True neither language is the "real" one, so a
    smoke test on English alone proves nothing about the Arabic site. The
    override also puts the language back afterwards: a request through the test
    client activates whatever it negotiated and never restores it, which reruns
    every later test in the wrong language.
    """
    with translation.override(language_code):
        url = home_page.url

        assert url.startswith(f"/{language_code}/")

        response = client.get(url, headers={"accept-language": language_code})

    assert response.status_code == 200
{%- else %}

def test_home_page_serves(client, home_page):
    response = client.get(home_page.url)

    assert response.status_code == 200
{%- endif %}


def test_home_page_renders_its_title(client, home_page):
    with translation.override(settings.LANGUAGE_CODE):
        url = home_page.url
        expected_title = home_page.title
        response = client.get(url)

    assert response.status_code == 200
    assert expected_title in response.content.decode()
{% if cookiecutter.multisite == "multi" %}

def test_one_home_page_per_site_root(home_page):
    """One per parent, not one per database: each site needs its own."""
    tree_root = Page.objects.get(depth=1)

    assert HomePage.can_create_at(tree_root) is False
{%- else %}

def test_only_one_home_page_may_exist(home_page):
    tree_root = Page.objects.get(depth=1)

    assert HomePage.can_create_at(tree_root) is False
{%- endif %}
