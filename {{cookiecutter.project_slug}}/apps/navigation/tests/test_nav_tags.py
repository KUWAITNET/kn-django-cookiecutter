"""Menu resolution, active state, and the header/footer partials."""

import json

import pytest
from django.template.loader import render_to_string
from django.test import RequestFactory
from wagtail.models import Site

from apps.navigation.models import FooterSettings, NavigationSettings
from apps.navigation.templatetags.navigation_tags import (
    nav_branch_active,
    nav_href,
    nav_item_active,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def site():
    return Site.objects.get(is_default_site=True)


@pytest.fixture
def menu(site):
    """A two-level menu: a page link with a child anchor, plus an external link."""
    root = site.root_page
    navigation = NavigationSettings.for_site(site)
    navigation.primary_menu = json.dumps(
        [
            {
                "type": "item",
                "value": {
                    "label": "Home",
                    "page": root.pk,
                    "url": "",
                    "children": [
                        {
                            "label": "Section",
                            "page": root.pk,
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
    return NavigationSettings.for_site(site).primary_menu


def test_menu_round_trips_through_the_setting(menu):
    labels = [block.value["label"] for block in menu]

    assert labels == ["Home", "Partner"]
    assert menu[0].value["children"][0]["label"] == "Section"


def test_nav_href_resolves_a_chosen_page(menu, site):
    assert nav_href(menu[0].value) == site.root_page.url


def test_nav_href_appends_an_anchor_to_the_page_url(menu, site):
    child = menu[0].value["children"][0]

    assert nav_href(child) == f"{site.root_page.url}#section"


def test_nav_href_passes_an_external_url_through(menu):
    assert nav_href(menu[1].value) == "https://example.com/partner/"


def test_nav_href_never_returns_an_empty_href():
    """A half-configured entry must stay inert, not reload the current page."""
    assert nav_href(None) == "#"
    assert nav_href({"label": "Nowhere", "page": None, "url": ""}) == "#"


def test_active_state_matches_the_served_path(menu, site):
    context = {"request": RequestFactory().get(site.root_page.url)}

    assert nav_item_active(context, menu[0].value) is True
    assert nav_item_active(context, menu[1].value) is False


def test_anchor_only_entries_are_never_active(menu, site):
    """The browser does not send the fragment, so matching one would be a guess."""
    context = {"request": RequestFactory().get(site.root_page.url)}
    child = menu[0].value["children"][0]

    assert nav_item_active(context, child) is False


def test_branch_active_covers_descendants(menu, site):
    context = {"request": RequestFactory().get(site.root_page.url)}

    assert nav_branch_active(context, menu[0].value) is True
    assert nav_branch_active(context, menu[1].value) is False


def test_header_renders_the_configured_menu(menu, site):
    request = RequestFactory().get(site.root_page.url)

    html = render_to_string("navigation/header.html", request=request)

    assert "Home" in html
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
