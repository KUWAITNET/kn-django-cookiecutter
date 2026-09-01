"""The admin edit form for a notification template.

Its one job is to put a "Reset to default" link next to each editable field.
The link is a real server round-trip (confirm, then POST, then reload the edit
page) rather than a client-side value swap, so it behaves the same whatever the
admin renders the field with.
"""

{% if cookiecutter.stack == "django" %}from django.forms import ModelForm as _ModelFormBase
{% endif %}from django.urls import reverse
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
{% if cookiecutter.stack == "wagtail" %}from wagtail.admin.forms.models import WagtailAdminModelForm as _ModelFormBase
{% endif %}
from apps.notifications.models import RESETTABLE_FIELDS

# The body is Django template source in a plain monospace textarea, deliberately
# not a rich-text editor. The reference project used one and inherited its
# round-trip rules: a block tag had to open and close inside a single paragraph,
# and a bare <br> crashed the edit view. Template source is code; it belongs in
# a code field.
BODY_WIDGET_ATTRS = {
    "rows": 16,
    "spellcheck": "false",
    "style": "font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;",
}

{% if cookiecutter.stack == "wagtail" %}#: Must match the viewset ``name`` in wagtail_hooks. Kept as a literal because
#: that module imports this one, not the other way round.
TEMPLATE_ADMIN_NAME = "notification-templates"
RESET_URL_NAME = f"{TEMPLATE_ADMIN_NAME}:reset-field"
{% else %}RESET_URL_NAME = "admin:notifications_notificationtemplate_reset_field"
{% endif %}


def reset_field_url(pk, field_name: str) -> str:
    return reverse(RESET_URL_NAME, args=[pk, field_name])


class NotificationTemplateForm(_ModelFormBase):
    """Adds the per-field "Reset to default" link.

    Built in ``__init__`` rather than declared statically because the URL needs
    ``self.instance.pk``, which does not exist when panels or fieldsets are
    defined at class level.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            return
        for field_name in RESETTABLE_FIELDS:
            field = self.fields.get(field_name)
            if field is None:
                continue
            field.help_text = format_html(
                '{} <a href="{}">{}</a>',
                field.help_text or "",
                reset_field_url(self.instance.pk, field_name),
                _("Reset to default"),
            )
