"""The five site settings: resolution, validation and the derived map URLs."""

from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from wagtail.models import Site

from apps.navigation.models import (
    BrandingSettings,
    ContactSettings,
    FooterSettings,
    NavigationSettings,
    SocialMediaSettings,
)

pytestmark = pytest.mark.django_db

ALL_SETTINGS = (
    BrandingSettings,
    ContactSettings,
    FooterSettings,
    NavigationSettings,
    SocialMediaSettings,
)


@pytest.fixture
def site():
    return Site.objects.get(is_default_site=True)


@pytest.mark.parametrize("model", ALL_SETTINGS)
def test_setting_resolves_for_the_current_site(site, model):
    assert model.for_site(site).site_id == site.pk


def test_contact_settings_have_no_raw_embed_field():
    """Regression guard on a deliberate security decision.

    A settings field holding an editor-supplied iframe or HTML snippet, rendered
    with |safe, is stored XSS on every page of the site. The map is built from
    coordinates instead, and this test exists so nobody reintroduces the field
    because it looked convenient.
    """
    field_names = {field.name for field in ContactSettings._meta.get_fields()}
    assert "map_embed" not in field_names
    assert "map_html" not in field_names


def test_coordinates_must_be_given_as_a_pair(site):
    contact = ContactSettings.for_site(site)
    contact.latitude = Decimal("29.375000")

    with pytest.raises(ValidationError) as excinfo:
        contact.full_clean()

    assert "longitude" in excinfo.value.message_dict


def test_map_urls_are_derived_from_the_coordinates(site):
    contact = ContactSettings.for_site(site)
    contact.latitude = Decimal("29.375000")
    contact.longitude = Decimal("47.977500")
    contact.map_zoom = 15

    assert contact.has_map
    assert contact.map_link_url.startswith("https://www.openstreetmap.org/")
    assert "29.375000" in contact.map_link_url
    assert contact.map_embed_url.startswith("https://www.openstreetmap.org/export/embed.html?bbox=")
    assert "marker=29.375000,47.977500" in contact.map_embed_url


def test_no_map_without_coordinates(site):
    contact = ContactSettings.for_site(site)

    assert not contact.has_map
    assert contact.map_link_url == ""
    assert contact.map_embed_url == ""


def test_social_links_list_only_the_configured_networks(site):
    social = SocialMediaSettings.for_site(site)
    social.facebook = "https://example.com/facebook"
    social.linkedin = "https://example.com/linkedin"

    names = [entry["name"] for entry in social.links]

    assert names == ["facebook", "linkedin"]
    assert social.links[0]["url"] == "https://example.com/facebook"
