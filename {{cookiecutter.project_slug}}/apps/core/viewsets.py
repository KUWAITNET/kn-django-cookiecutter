"""Reusable admin viewset bases."""

from wagtail.admin.viewsets.model import ModelViewSet
{%- if cookiecutter.multisite == "multi" %}
from wagtail.snippets.views.chooser import SnippetChooserViewSet
{%- endif %}


class NoAddModelViewSet(ModelViewSet):
    """A ``ModelViewSet`` with the "add" view and action removed.

    For records that must only ever be created by something other than a staff
    member typing into a form - a visitor submitting a form, an import, a webhook.
    Hand-creating a submission makes the submission log a fiction, so the route
    is removed rather than hidden.
    """

    def get_urlpatterns(self):
        return [
            pattern
            for pattern in super().get_urlpatterns()
            if getattr(pattern, "name", "") != "add"
        ]

    def get_common_view_kwargs(self, **kwargs):
        return super().get_common_view_kwargs(add_url_name=None, **kwargs)
{%- if cookiecutter.multisite == "multi" %}


class SiteFilteredSnippetChooserViewSet(SnippetChooserViewSet):
    """Chooser viewset for site-scoped snippets, filterable by ``sites__id``.

    Pairs with ``apps.core.blocks.SiteFilteredSnippetChooserBlock``, which bakes
    the editing page's site into the modal URL as this query parameter. It only
    filters the admin modal: front-end code must still call ``.for_site()``.
    """

    url_filter_parameters = ["sites__id"]
    preserve_url_parameters = [*SnippetChooserViewSet.preserve_url_parameters, "sites__id"]
{%- endif %}
