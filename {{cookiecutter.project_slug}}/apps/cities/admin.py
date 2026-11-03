"""Django-admin surface for the country reference data.

django-unfold is the company standard wherever ``django.contrib.admin`` is
mounted, which is both stacks{% if cookiecutter.stack == "wagtail" %} - on this one the Django admin hosts the models
that have no CMS interface, and ``wagtail_hooks.py`` mirrors this listing into the
CMS admin for editors who never leave it{% endif %}.
"""

from django.contrib import admin
from django.contrib.admin.exceptions import NotRegistered
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin

from apps.cities.models import Country

#: Imported from GeoNames on every ``manage.py cities_light`` run. Shown so an
#: editor can see what they are toggling, never editable: a hand-edited value is
#: silently overwritten by the next import, which is worse than not offering it.
GEONAMES_FIELDS = ["name", "code2", "code3", "continent", "tld", "phone", "geoname_id"]

# cities-light registers its own plain-admin class for Country as soon as it is
# imported, and it sits earlier in INSTALLED_APPS - so ours replaces it rather
# than being added alongside, which would raise AlreadyRegistered at startup.
# Region/SubRegion/City keep the library's admin: they carry no project-owned
# column, and a project that never imports cities never opens them.
try:
    admin.site.unregister(Country)
except NotRegistered:
    pass


@admin.register(Country)
class CountryAdmin(ModelAdmin):
    """Toggle which countries the public forms offer.

    ``is_active`` is editable straight from the list, because the realistic task
    is "turn off these forty countries", not "open forty change forms".
    """

    list_display = ["name", "code2", "phone_code_display", "continent", "is_active"]
    list_display_links = ["name"]
    list_editable = ["is_active"]
    list_filter = ["is_active", "continent"]
    search_fields = ["name", "code2", "code3", "phone"]
    list_per_page = 50
    ordering = ["name"]
    readonly_fields = GEONAMES_FIELDS
    fieldsets = [
        (
            _("Imported from GeoNames"),
            {"fields": GEONAMES_FIELDS},
        ),
        (
            _("Editable"),
            {
                "fields": [
{%- if cookiecutter.languages == "en_ar" %}
                    "display_name_en",
                    "display_name_ar",
{%- else %}
                    "display_name",
{%- endif %}
                    "is_active",
                ]
            },
        ),
    ]

    @admin.display(description=_("Phone code"), ordering="phone")
    def phone_code_display(self, obj):
        return obj.phone_code or "-"

    def has_add_permission(self, request):
        # Countries arrive from the importer. A hand-added row has no geoname_id,
        # so the next import creates a duplicate rather than updating it.
        return False

    def has_delete_permission(self, request, obj=None):
        # Deleting is how you lose a submission's country FK. Deactivate instead.
        return False
