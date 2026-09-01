{%- if cookiecutter.api == "headless" -%}
"""CMS content API contract tests (api-standard.md A13).

The field allowlist is the whole security model here, and "only live public
pages" is the whole visibility model. Both are asserted, because both are one
careless ``api_fields`` edit away from publishing something nobody reviewed.
"""

import pytest
from django.urls import reverse
from wagtail.models import Page, PageViewRestriction, Site

pytestmark = pytest.mark.django_db


@pytest.fixture
def site_root():
    return Site.objects.get(is_default_site=True).root_page


def add_page(parent, title, slug, live=True):
    page = Page(title=title, slug=slug, live=live)
    parent.add_child(instance=page)
    return page


def listing_url():
    return reverse("wagtailapi:pages:listing")


def titles(response):
    return {item["title"] for item in response.json()["items"]}


def test_the_content_api_is_readable_without_credentials(client, site_root):
    """Explicitly public: it serves the published site's own content."""
    add_page(site_root, "Published page", "published-page")

    response = client.get(listing_url())

    assert response.status_code == 200
    assert "Published page" in titles(response)


def test_a_draft_page_is_not_served(client, site_root):
    add_page(site_root, "Draft page", "draft-page", live=False)

    assert "Draft page" not in titles(client.get(listing_url()))


def test_a_restricted_page_is_not_served(client, site_root):
    restricted = add_page(site_root, "Members only", "members-only")
    PageViewRestriction.objects.create(
        page=restricted,
        restriction_type=PageViewRestriction.PASSWORD,
        password="a-shared-password",
    )

    assert "Members only" not in titles(client.get(listing_url()))


def test_the_listing_returns_only_the_declared_fields(client, site_root):
    from apps.api.wagtail_api import ContentPagesAPIViewSet

    add_page(site_root, "Published page", "published-page")

    item = client.get(listing_url()).json()["items"][0]

    assert set(item) <= set(ContentPagesAPIViewSet.listing_default_fields) | {"meta"}


def test_fields_wildcard_cannot_widen_the_allowlist(client, site_root):
    """``?fields=*`` returns the declared allowlist - that is the entire model."""
    from apps.api.wagtail_api import ContentPagesAPIViewSet

    add_page(site_root, "Published page", "published-page")

    item = client.get(listing_url(), {"fields": "*"}).json()["items"][0]

    allowed = set(ContentPagesAPIViewSet.body_fields) | {"meta"}
    assert set(item) <= allowed
    assert set(item["meta"]) <= set(ContentPagesAPIViewSet.meta_fields)


def test_the_content_api_is_absent_from_the_application_schema(client):
    from apps.api.wagtail_api import ContentPagesAPIViewSet

    assert ContentPagesAPIViewSet.schema is None
{% endif -%}
