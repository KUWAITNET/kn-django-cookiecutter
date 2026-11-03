{%- if cookiecutter.languages == "en_ar" -%}
"""Translated fields on the site settings.

The menu StreamFields are translated too, so each language gets its own menu
tree. That is deliberate: Arabic navigation is rarely a word-for-word copy of the
English one, and forcing a shared structure is how sites end up with an English
label inside an Arabic dropdown.
"""

from modeltranslation.translator import TranslationOptions, register

from apps.navigation.models import ContactSettings, FooterSettings, NavigationSettings


@register(ContactSettings)
class ContactSettingsTranslation(TranslationOptions):
    fields = ("address", "working_hours", "map_label")


@register(FooterSettings)
class FooterSettingsTranslation(TranslationOptions):
    fields = (
        "about_text",
        "footer_menu",
{%- if cookiecutter.newsletter == "yes" %}
        "newsletter_heading",
{%- endif %}
        "copyright_text",
    )


@register(NavigationSettings)
class NavigationSettingsTranslation(TranslationOptions):
    fields = ("primary_menu",)
{%- endif %}
