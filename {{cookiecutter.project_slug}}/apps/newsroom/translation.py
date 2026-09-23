"""Translated fields on the newsroom models.

An article's slug is deliberately not translated: it keeps one address across
languages, so the language switcher and the sitemap alternates never miss.
"""

from modeltranslation.translator import TranslationOptions, register

from apps.core.translation import BasePageTranslationOptions
from apps.newsroom.models import NewsArticle, NewsCategory, NewsIndexPage


@register(NewsCategory)
class NewsCategoryTranslation(TranslationOptions):
    fields = ("name",)


@register(NewsArticle)
class NewsArticleTranslation(TranslationOptions):
    fields = ("title", "introduction", "body", "search_description")


@register(NewsIndexPage)
class NewsIndexPageTranslation(TranslationOptions):
    fields = BasePageTranslationOptions.fields
