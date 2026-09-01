"""Application configuration for the core app.

``KuwaitnetAdminConfig`` deliberately lives in ``apps.core.admin_config`` and not
here: Django discovers the app config for the ``apps.core`` entry by scanning this
module for ``AppConfig`` subclasses, and two candidates in one module makes that
discovery ambiguous.
"""

from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.core"
    # Short label: "core.CustomImage"-style references depend on it.
    label = "core"
    verbose_name = "Core"

    def ready(self):
        # Importing the module is what registers the system checks and, on the
        # bilingual CMS stack, installs the localised page-URL patch.
{%- if cookiecutter.stack == "wagtail" and cookiecutter.languages == "en_ar" %}
        from apps.core import checks, url_patches  # noqa: F401
{%- else %}
        from apps.core import checks  # noqa: F401
{%- endif %}
