"""Application configuration for the search app."""

from django.apps import AppConfig


class SearchConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.search"
    label = "search"
    verbose_name = "Search"
{%- if cookiecutter.languages == "en_ar" %}

    def ready(self):
        # Without this, a search in Arabic matches English columns and returns
        # nothing at all. See apps.search.indexing.
        from apps.search.indexing import register_translated_search_fields

        register_translated_search_fields()
{%- endif %}
