"""The home page.

Its body is a StreamField over ``apps.core.blocks.HOME_BLOCKS`` rather than a
fixed set of model fields, so the client can reorder and switch off whole
sections of the landing page without a deployment. Blocks are defined once in
``apps.core.blocks`` and shared with every other page type; nothing block-shaped
belongs in this module.
"""

from django.utils.translation import gettext_lazy as _
from wagtail.admin.panels import FieldPanel
from wagtail.fields import StreamField
from wagtail.search import index

from apps.core.blocks import HOME_BLOCKS
from apps.core.models import BasePage


class HomePage(BasePage):
    """The site's landing page.

    Inherits ``BasePage`` so the home page carries the same SEO and hero fields
    as every other page - a landing page that quietly lacks a share image or an
    introduction is the usual reason a site launches with a blank social preview.
    """
{% if cookiecutter.multisite == "multi" %}
    # One home page per parent, not one per database: ``max_count`` caps the
    # whole installation at a single instance, which is precisely wrong when
    # several sites share this database.
    max_count_per_parent = 1
{%- else %}
    max_count = 1
{%- endif %}
    # Only ever created directly under the tree root, as a site's root page.
    parent_page_types = ["wagtailcore.Page"]

    body = StreamField(HOME_BLOCKS, blank=True, collapsed=True, verbose_name=_("Body"))

    content_panels = BasePage.content_panels + [FieldPanel("body")]

    search_fields = BasePage.search_fields + [index.SearchField("body")]

    class Meta:
        verbose_name = _("Home page")
