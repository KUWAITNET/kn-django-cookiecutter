{%- if cookiecutter.languages == "en_ar" and cookiecutter.stack == "wagtail" %}
"""Translated fields on the contact page.

Only the editor-authored copy is translated. ``ContactSubmission`` is not: a
visitor's message is in whatever language they wrote it in, and a per-language
column would imply that somebody maintains a second version of it.
"""

from modeltranslation.translator import TranslationOptions, register

from apps.contact.models import ContactPage
from apps.core.translation import BasePageTranslationOptions


@register(ContactPage)
class ContactPageTranslation(TranslationOptions):
    fields = (*BasePageTranslationOptions.fields, "intro", "thank_you_text")
{%- endif %}
