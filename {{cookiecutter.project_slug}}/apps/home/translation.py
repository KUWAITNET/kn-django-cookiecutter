{%- if cookiecutter.languages == "en_ar" -%}
"""Translated fields on the home page.

``BasePageTranslationOptions`` carries the fields every page shares, so adding a
field to the base page does not mean editing one translation module per app.
"""

from modeltranslation.translator import TranslationOptions, register

from apps.core.translation import BasePageTranslationOptions
from apps.home.models import HomePage


@register(HomePage)
class HomePageTranslation(TranslationOptions):
    fields = (*BasePageTranslationOptions.fields, "body")
{%- endif %}
