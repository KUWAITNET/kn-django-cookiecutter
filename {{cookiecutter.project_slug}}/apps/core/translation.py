{% if cookiecutter.languages == "en_ar" -%}
{%- if cookiecutter.stack == "wagtail" -%}
"""Translation registration for core models.

modeltranslation can only register concrete models, but every content page
inherits the same abstract base - so the shared field list lives here as
``BasePageTranslationOptions`` and each app's ``translation.py`` spreads it::

    @register(NewsPage)
    class NewsPageTR(TranslationOptions):
        fields = (*BasePageTranslationOptions.fields, "body")

The page's own ``title``, ``slug``, ``seo_title``, ``search_description`` and
``url_path`` are registered automatically by wagtail-modeltranslation. That is
what creates ``slug_en``/``slug_ar``, and therefore what makes a language
switcher that only swaps the URL prefix wrong (see ``core_tags``).
"""

from modeltranslation.translator import TranslationOptions, register

from apps.core.models import CustomImage


class BasePageTranslationOptions(TranslationOptions):
    """The fields every page type translates."""

    fields = ("hero_subtitle", "introduction")


@register(CustomImage)
class CustomImageTR(TranslationOptions):
    fields = ("caption",)
{%- else -%}
"""Translation registration for core models.

Core has no translatable concrete models of its own: ``TimeStampedModel`` is
abstract and carries no editorial text. Each app registers its own models in its
own ``translation.py``, which django-modeltranslation autodiscovers::

    from modeltranslation.translator import TranslationOptions, register

    @register(Article)
    class ArticleTR(TranslationOptions):
        fields = ("title", "body")

Remember to run ``makemigrations`` after adding a registration: modeltranslation
adds one real column per field per language.
"""
{%- endif %}
{%- endif %}
