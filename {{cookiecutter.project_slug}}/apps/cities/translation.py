{%- if cookiecutter.languages == "en_ar" %}
"""Translation registration for the country reference data.

Only ``display_name`` is translated. ``name`` and the other GeoNames columns are
owned by the importer: giving them per-language columns would mean the importer
writing into whichever language happened to be active when it ran, and the
alternate-name blob (``translations``, filled from
``CITIES_LIGHT_TRANSLATION_LANGUAGES``) already carries the imported names.

So the two sources layer: the imported Arabic name is used by default, and
``display_name_ar`` is the editor's override for the ones GeoNames gets wrong.
"""

from modeltranslation.translator import TranslationOptions, register

from apps.cities.models import Country


@register(Country)
class CountryTranslationOptions(TranslationOptions):
    fields = ("display_name",)
{%- endif %}
