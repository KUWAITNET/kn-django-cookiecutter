"""The home page serves, in every configured language."""

import pytest
{%- if cookiecutter.languages == "en_ar" %}
from django.utils import translation
{%- endif %}
from wagtail.models import Page, Site

from apps.home.models import HomePage

pytestmark = pytest.mark.django_db


@pytest.fixture
def home_page():
    """A published home page, installed as the default site's root."""
    tree_root = Page.objects.get(depth=1)
    page = HomePage(title="Home", slug="home-page")
    tree_root.add_child(instance=page)

    site = Site.objects.get(is_default_site=True)
    site.root_page = page
    site.save()
    return page
{% if cookiecutter.languages == "en_ar" %}

@pytest.mark.parametrize("language_code", ["en", "ar"])
def test_home_page_serves_in_each_language(client, home_page, language_code):
    """Both prefixes must serve.

    With prefix_default_language=True neither language is the "real" one, so a
    smoke test on English alone proves nothing about the Arabic site.
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
    response = client.get(home_page.url)

    assert "Home" in response.content.decode()
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
