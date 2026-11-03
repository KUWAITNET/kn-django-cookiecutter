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
        # Importing the module is what registers the system checks{% if cookiecutter.stack == "wagtail" and cookiecutter.languages == "en_ar" %} and, on the
        # bilingual CMS stack, installs the localised page-URL patch{% endif %}.
{%- if cookiecutter.stack == "wagtail" and cookiecutter.use_2fa == "yes" %}
        # otp_patches makes wagtail-2fa's sign-in form work with django-otp 1.7+.
{%- endif %}
        from apps.core import checks{% if cookiecutter.stack == "wagtail" and cookiecutter.use_2fa == "yes" %}, otp_patches{% endif %}{% if cookiecutter.stack == "wagtail" and cookiecutter.languages == "en_ar" %}, url_patches{% endif %}  # noqa: F401
