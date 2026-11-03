{% if cookiecutter.stack == "wagtail" -%}
"""CMS admin surface for the country reference data.

The same toggle listing as ``admin.py``, mirrored into the CMS admin so an editor
never has to leave it to turn a country off. It lives in this app rather than in
the app that consumes countries: in the project this template is derived from the
listing sat in ``apps/contact/wagtail_hooks.py``, which made the countries app
impossible to lift out on its own.
"""

from django.utils.translation import gettext_lazy as _
from wagtail import hooks
from wagtail.admin.panels import FieldPanel
from wagtail.admin.ui.tables import BooleanColumn

from apps.cities.models import Country
from apps.core.viewsets import NoAddModelViewSet


class CountryViewSet(NoAddModelViewSet):
    """Toggle countries active or inactive for the public form dropdowns.

    Adding is disabled (``NoAddModelViewSet``): rows come from
    ``manage.py cities_light`` and a hand-added one has no GeoNames id, so the
    next import duplicates it instead of updating it.
    """

    model = Country
    name = "countries"
    icon = "site"
    menu_label = _("Countries")
    menu_order = 800
    add_to_admin_menu = True
    copy_view_enabled = False
    list_per_page = 50
    ordering = ["name"]
    list_display = [
        "name",
        "code2",
        "phone",
        "continent",
        BooleanColumn("is_active", label=_("Active")),
    ]
    list_filter = ["is_active", "continent"]
    search_fields = ["name", "code2", "code3", "phone"]
    # Only the two columns this project owns. Every other field is GeoNames-owned
    # and a hand-edited value is silently overwritten by the next import.
    panels = [
{%- if cookiecutter.languages == "en_ar" %}
        FieldPanel("display_name_en"),
        FieldPanel("display_name_ar"),
{%- else %}
        FieldPanel("display_name"),
{%- endif %}
        FieldPanel("is_active"),
    ]


@hooks.register("register_admin_viewset")
def register_country_viewset():
    return CountryViewSet()
{%- endif %}
