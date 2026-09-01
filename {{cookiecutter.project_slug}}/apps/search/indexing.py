{%- if cookiecutter.languages == "en_ar" -%}
"""Index the translated columns, not only the base ones.

Per-field translation stores every language in its own column (``introduction_ar``
next to ``introduction``), but a model's ``search_fields`` still names the base
field only. With the database search backend that means an Arabic query is
matched against English text and returns nothing - no error, no warning, just an
empty results page. It is the most common "search is broken" report on our
bilingual sites and the reason this module exists.

Doing it here, once, is deliberate: the alternative is asking every page model to
remember to list ``title_ar``, ``introduction_ar`` and so on, which works right
up until somebody adds a model and forgets.
"""

from django.conf import settings
from wagtail.search import index


def _language_suffixes():
    """Column suffixes added by the translation layer, excluding the base column."""
    default = settings.MODELTRANSLATION_DEFAULT_LANGUAGE
    return [code.replace("-", "_") for code, _label in settings.LANGUAGES if code != default]


def _concrete_field_names(model):
    return {field.name for field in model._meta.get_fields() if getattr(field, "concrete", False)}


def _translated_variants(model, suffixes):
    """Search fields for every translated column that exists on ``model``."""
    concrete = _concrete_field_names(model)
    declared = {(type(field).__name__, field.field_name) for field in model.search_fields}
    variants = []

    for field in model.search_fields:
        if not isinstance(field, index.SearchField | index.AutocompleteField):
            continue
        for suffix in suffixes:
            name = f"{field.field_name}_{suffix}"
            key = (type(field).__name__, name)
            if name not in concrete or key in declared:
                continue
            declared.add(key)
            if isinstance(field, index.SearchField):
                variants.append(index.SearchField(name, boost=getattr(field, "boost", 1)))
            else:
                variants.append(index.AutocompleteField(name))

    return variants


def register_translated_search_fields():
    """Extend every indexed model's search fields with its translated columns.

    Idempotent, because ``AppConfig.ready`` runs twice under the autoreloader.
    """
    suffixes = _language_suffixes()
    if not suffixes:
        return

    for model in index.get_indexed_models():
        variants = _translated_variants(model, suffixes)
        if not variants:
            continue
        # Assign a fresh list rather than appending: models that do not declare
        # their own ``search_fields`` share the inherited list object, and
        # mutating it in place would leak one model's columns into its siblings.
        model.search_fields = list(model.search_fields) + variants
{%- endif %}
