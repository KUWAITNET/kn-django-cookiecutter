from django.apps import AppConfig


class ApiConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.api"
    label = "api"
    verbose_name = "API"
{%- if cookiecutter.stack == "wagtail" %}

    def ready(self):
        _exclude_cms_admin_api_from_schema()


def _exclude_cms_admin_api_from_schema() -> None:
    """Keep the CMS admin's own API out of our OpenAPI document.

    The CMS admin mounts DRF viewsets under the admin URL prefix to drive its own
    editing interface. They sit behind the admin login, they are internal, and
    they are not part of the contract we publish - but drf-spectacular enumerates
    every DRF view reachable from the root URLconf, and it cannot describe these
    ones: their serializers need a router attached to the request and a live
    collection table. Left alone they emit dozens of generation errors, which
    would make ``--fail-on-warn`` useless exactly when it matters.

    ``schema = None`` is DRF's own opt-out and is read at generation time, so it
    applies however the URLs were built.
    """
    from django.utils.module_loading import import_string

    for dotted_path in (
        "wagtail.admin.api.views.PagesAdminAPIViewSet",
        "wagtail.images.api.admin.views.ImagesAdminAPIViewSet",
        "wagtail.documents.api.admin.views.DocumentsAdminAPIViewSet",
    ):
        try:
            import_string(dotted_path).schema = None
        except ImportError:
            # An upgrade moved it. The next schema build will say so loudly,
            # which is the right time to find out.
            continue
{%- endif %}
