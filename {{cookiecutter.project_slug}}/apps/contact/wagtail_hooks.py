{% if cookiecutter.stack == "wagtail" -%}
"""CMS admin surface for contact submissions.

``NoAddModelViewSet`` plus panels that are all ``read_only``: a submission is
evidence of what a visitor sent, and an editor who can change it makes it an
assertion instead. ``list_export`` gives the CSV/XLSX button, which is the
legitimate way to get the data out.
"""

from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from wagtail import hooks
from wagtail.admin.panels import FieldPanel, MultiFieldPanel, Panel
from wagtail.admin.ui.tables import {% if cookiecutter.countries_app != "none" %}Column, {% endif %}DateColumn

from apps.contact.models import ContactSubmission
from apps.core.viewsets import NoAddModelViewSet


class PrivateAttachmentPanel(Panel):
    """Links an attachment through the permission gate.

    ``FieldPanel(read_only=True)`` on a file field renders the storage path, and
    a link built from that would bypass every check. This one goes through
    ``/files/`` (``apps.core.views.private_file``), which checks the model's
    entry in ``PRIVATE_FILE_PERMISSIONS`` on every click.
    """

    def __init__(self, field_name="attachment", **kwargs):
        kwargs.setdefault("heading", _("Attachment"))
        super().__init__(**kwargs)
        self.field_name = field_name

    def clone_kwargs(self):
        # Panels are cloned when they are bound; without this the field name is
        # lost and the clone renders the wrong column.
        kwargs = super().clone_kwargs()
        kwargs["field_name"] = self.field_name
        return kwargs

    class BoundPanel(Panel.BoundPanel):
        def render_html(self, parent_context=None):
            attachment = getattr(self.instance, self.panel.field_name, None)
            if not attachment:
                return format_html(
                    '<div class="w-panel__wrapper"><h2>{}</h2><p>{}</p></div>',
                    self.panel.heading,
                    _("No attachment."),
                )
            return format_html(
                '<div class="w-panel__wrapper"><h2>{}</h2>'
                '<p><a href="{}" rel="noopener noreferrer">{}</a></p></div>',
                self.panel.heading,
                self.instance.attachment_download_url,
                self.instance.attachment_original_name or attachment.name,
            )


class ContactSubmissionViewSet(NoAddModelViewSet):
    """Submissions received through the contact form."""

    model = ContactSubmission
    name = "contact-submissions"
    icon = "mail"
    menu_label = _("Contact submissions")
    menu_order = 810
    add_to_admin_menu = True
    copy_view_enabled = False
    inspect_view_enabled = False
    list_per_page = 50
    ordering = ["-submitted_at"]
    list_display = [
        "full_name",
        "email",
{%- if cookiecutter.countries_app != "none" %}
        # The readable name, not the stored value: what a country is stored as
        # differs per backend and no admin surface should have to know.
        Column("country_name", label=_("Country")),
{%- endif %}
        "enquiry_type",
        "subject",
{%- if cookiecutter.multisite == "multi" %}
        "site",
{%- endif %}
        DateColumn("submitted_at", label=_("Submitted")),
    ]
    list_filter = [
        "enquiry_type",
{%- if cookiecutter.countries_app != "none" %}
        "country",
{%- endif %}
{%- if cookiecutter.multisite == "multi" %}
        "site",
{%- endif %}
    ]
    search_fields = ["full_name", "email", "company_name", "subject", "message"]
    list_export = [
        "full_name",
        "company_name",
        "email",
        "phone",
{%- if cookiecutter.countries_app != "none" %}
        "country_name",
{%- endif %}
        "enquiry_type",
        "subject",
        "message",
        "attachment_original_name",
        "submitted_at",
    ]
    panels = [
        MultiFieldPanel(
            [
                FieldPanel("full_name", read_only=True),
                FieldPanel("company_name", read_only=True),
                FieldPanel("email", read_only=True),
                FieldPanel("phone", read_only=True),
            ],
            heading=_("Sender"),
        ),
        MultiFieldPanel(
            [
{%- if cookiecutter.countries_app != "none" %}
                FieldPanel("country", read_only=True),
{%- endif %}
                FieldPanel("enquiry_type", read_only=True),
                FieldPanel("submitted_at", read_only=True),
{%- if cookiecutter.multisite == "multi" %}
                FieldPanel("site", read_only=True),
{%- endif %}
            ],
            heading=_("Details"),
        ),
        MultiFieldPanel(
            [
                FieldPanel("subject", read_only=True),
                FieldPanel("message", read_only=True),
            ],
            heading=_("Message"),
        ),
        PrivateAttachmentPanel(),
    ]


@hooks.register("register_admin_viewset")
def register_contact_submission_viewset():
    return ContactSubmissionViewSet()
{%- endif %}
