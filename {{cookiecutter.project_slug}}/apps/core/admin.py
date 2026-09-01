"""Django-admin registration for the site-wide configuration singleton.

Autodiscovered by ``apps.core.admin_config.KuwaitnetAdminConfig``, so it is served
from the Unfold-skinned admin site like every other model.
"""

from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from solo.admin import SingletonModelAdmin
from unfold.admin import ModelAdmin

{% if cookiecutter.stack == "wagtail" -%}
from apps.core.models import OperationalSettings
{%- else -%}
from apps.core.models import SiteConfiguration
{%- endif %}


class SingletonAdmin(SingletonModelAdmin, ModelAdmin):
    """django-solo's single-row behaviour, rendered by Unfold.

    ``SingletonModelAdmin`` comes first in the MRO so its URL map wins: the
    changelist route is replaced by the change form for row 1, and adding and
    deleting are refused. Unfold supplies everything visual.

    The two template attributes are reset on purpose. django-solo ships its own
    ``change_form``/``object_history`` templates whose only content is a
    hand-written breadcrumb trail and object-tools list copied from the stock
    Django admin; inside the Unfold shell those render as unstyled markup halfway
    down the page. Falling back to whatever Unfold sets restores the skin, and
    costs only a breadcrumb that pointed at a changelist this admin does not have.
    """

    change_form_template = ModelAdmin.change_form_template
    object_history_template = ModelAdmin.object_history_template

{% if cookiecutter.stack == "wagtail" -%}

@admin.register(OperationalSettings)
class OperationalSettingsAdmin(SingletonAdmin):
    """Installation-wide operational configuration.

    Deliberately not a Wagtail setting: these are switches an administrator flips,
    they apply to every site in the installation, and they have no place in an
    editor's day. See the model docstring for where the line falls.
    """

    fieldsets = [
        (
            _("Integrations"),
            {
                "fields": ["outbound_integrations_enabled"],
                "description": _(
                    "Applies to every site served by this installation, not to one site."
                ),
            },
        ),
        (_("Operations"), {"fields": ["technical_alert_email"]}),
    ]
{%- else -%}

@admin.register(SiteConfiguration)
class SiteConfigurationAdmin(SingletonAdmin):
    """The site's own settings: branding, contact details and social profiles."""

    fieldsets = [
        (
            _("Identity"),
            {
                "fields": ["site_name", "logo", "default_share_image"],
                "description": _(
                    "Leave a field empty to keep the value the project was deployed with."
                ),
            },
        ),
        (_("Contact"), {"fields": ["contact_email", "contact_phone", "address"]}),
        (
            _("Social profiles"),
            {
                "fields": ["facebook", "x_twitter", "instagram", "linkedin", "youtube", "tiktok"],
                "description": _("Only the profiles you fill in are rendered."),
            },
        ),
    ]
{%- endif %}
