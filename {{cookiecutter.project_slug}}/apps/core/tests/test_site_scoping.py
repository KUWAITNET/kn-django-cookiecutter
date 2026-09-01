"""Site scoping in a multi-site install.

Sites share one database, so an unscoped query silently returns another site's
content. These pin the two scoping primitives everything else is built on.
"""

import pytest
from wagtail.models import Page, Site

from apps.core.models import SiteFilterableQuerySet, SiteScopedPageQuerySet

pytestmark = pytest.mark.django_db


def test_page_scoping_restricts_to_one_site_tree():
    site = Site.objects.get(is_default_site=True)
    scoped = SiteScopedPageQuerySet(model=Page).for_site(site)
    assert list(scoped) == list(Page.objects.descendant_of(site.root_page))


def test_page_scoping_is_a_no_op_without_a_site():
    # Block previews and management commands have no site; they must get the
    # unscoped queryset back rather than an empty one.
    queryset = SiteScopedPageQuerySet(model=Page)
    assert queryset.for_site(None) is queryset


def test_filterable_scoping_is_a_no_op_without_a_site():
    queryset = SiteFilterableQuerySet(model=Site)
    assert queryset.for_site(None) is queryset


def test_every_site_has_its_own_root_page():
    roots = list(Site.objects.values_list("root_page_id", flat=True))
    # Two sites sharing a root page means one of them serves the other's content.
    assert len(roots) == len(set(roots))
