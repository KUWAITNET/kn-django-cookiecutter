"""Menu resolution, active state, and the header/footer partials."""

import json

import pytest
from django.template.loader import render_to_string
from django.test import RequestFactory
from wagtail.models import Page, Site

from apps.navigation.models import FooterSettings, NavigationSettings
from apps.navigation.templatetags.navigation_tags import (
    UNRESOLVED_HREF,
    nav_branch_active,
    nav_href,
    nav_item_active,
)

pytestmark = pytest.mark.django_db


def new_page(title, slug):
    """Build a page with every translated column filled in.

    The per-language columns are not optional - the default-language one is
    required - and the language active during a test is whatever the previous
    test left behind. Setting only the base ``title`` therefore fails, and fails
    intermittently, which is the worst way for it to fail.
    """
    page = Page(title=title, slug=slug)
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
def about_page(site):
    """A published page inside the site's tree, so it has a resolvable URL.

    Everything here hangs off the seeded site root rather than repointing the
    default Site at a new page. A test that repoints it poisons Wagtail's cached
    site root paths, which live in the Django cache and are NOT rolled back with
    the test transaction - every later test then sees ``page.url`` return None.
    """
    page = new_page("About us", "about-us")
    site.root_page.add_child(instance=page)
    return page


@pytest.fixture
def team_page(about_page):
    """A page one level below ``about_page``, for branch-active matching."""
    page = new_page("Team", "team")
    about_page.add_child(instance=page)
    return page


@pytest.fixture
def menu(site, about_page):
    """A two-level menu: a page link with a child anchor, plus an external link."""
    navigation = NavigationSettings.for_site(site)
    navigation.primary_menu = json.dumps(
        [
            {
                "type": "item",
                "value": {
                    "label": "About",
                    "page": about_page.pk,
                    "url": "",
                    "children": [
                        {
                            "label": "Section",
                            "page": about_page.pk,
                            "url": "#section",
                            "children": [],
                        }
                    ],
                },
            },
            {
                "type": "item",
                "value": {
                    "label": "Partner",
                    "page": None,
                    "url": "https://example.com/partner/",
                    "children": [],
                },
            },
        ]
    )
    navigation.save()
    return navigation.primary_menu


def test_menu_round_trips_through_the_setting(menu):
    labels = [block.value["label"] for block in menu]

    assert labels == ["About", "Partner"]
    assert menu[0].value["children"][0]["label"] == "Section"


def test_nav_href_resolves_a_chosen_page(menu, about_page):
    resolved = nav_href(menu[0].value)

    assert resolved == about_page.url
    assert resolved != UNRESOLVED_HREF


def test_nav_href_appends_an_anchor_to_the_page_url(menu, about_page):
    child = menu[0].value["children"][0]

    assert nav_href(child) == f"{about_page.url}#section"


def test_nav_href_passes_an_external_url_through(menu):
    assert nav_href(menu[1].value) == "https://example.com/partner/"


def test_nav_href_never_returns_an_empty_href():
    """A half-configured entry must stay inert, not reload the current page."""
    assert nav_href(None) == UNRESOLVED_HREF
    assert nav_href({"label": "Nowhere", "page": None, "url": ""}) == UNRESOLVED_HREF


def test_an_unroutable_page_resolves_to_a_single_hash():
    """A page outside every site's tree has no URL.

    The contract is one inert "#": never the string "None" from a formatted URL,
    and never a doubled "##section" from an anchor glued onto nothing.
    """
    orphan = new_page("Orphan", "orphan")
    Page.objects.get(depth=1).add_child(instance=orphan)

    assert orphan.url is None
    assert nav_href({"label": "Orphan", "page": orphan, "url": ""}) == UNRESOLVED_HREF
    assert nav_href({"label": "Orphan", "page": orphan, "url": "#section"}) == UNRESOLVED_HREF


def test_active_state_matches_the_served_path(menu, about_page):
    """The served path carries a language prefix; both sides must normalise the same."""
    context = {"request": RequestFactory().get(about_page.url)}

    assert nav_item_active(context, menu[0].value) is True
    assert nav_item_active(context, menu[1].value) is False


def test_anchor_only_entries_are_never_active(menu, about_page):
    """The browser does not send the fragment, so matching one would be a guess."""
    context = {"request": RequestFactory().get(about_page.url)}
    child = menu[0].value["children"][0]

    assert nav_item_active(context, child) is False


def test_branch_active_covers_descendants(menu, team_page):
    """A child page keeps its parent's entry highlighted, without marking it current."""
    context = {"request": RequestFactory().get(team_page.url)}

    assert nav_branch_active(context, menu[0].value) is True
    assert nav_item_active(context, menu[0].value) is False
    assert nav_branch_active(context, menu[1].value) is False


def test_header_renders_the_configured_menu(menu, about_page):
    request = RequestFactory().get(about_page.url)

    html = render_to_string("navigation/header.html", request=request)

    assert "About" in html
    assert "https://example.com/partner/" in html
    assert "site-nav__dropdown" in html


def test_footer_renders_settings_content(site):
    footer = FooterSettings.for_site(site)
    footer.copyright_text = "Example Client W.L.L."
    footer.about_text = "A short description."
    footer.save()
    request = RequestFactory().get("/")

    html = render_to_string("navigation/footer.html", request=request)

    assert "Example Client W.L.L." in html
    assert "A short description." in html
{% raw %}

def test_the_partials_leak_no_template_syntax(menu, about_page):
    """Nothing unrendered may reach the page.

    Django's ``{# ... #}`` comment is single-line only: a multi-line one is not
    tokenised as a comment at all and renders verbatim into the markup, in front
    of the visitor. Checking for leftover syntax catches that, and every other
    variant of it, instead of only the strings a test thought to look for.
    """
    request = RequestFactory().get(about_page.url)

    for template_name in ("navigation/header.html", "navigation/footer.html"):
        html = render_to_string(template_name, request=request)

        assert "{#" not in html
        assert "{%" not in html
        assert "{{" not in html
{%- endraw %}
