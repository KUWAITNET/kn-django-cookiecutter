"""Read-only admin for contact submissions.

Nobody hand-edits a submission. A row here is what a visitor sent, and an
administrator who can change it turns the submission log into an assertion rather
than evidence - which matters the first time one is quoted in a dispute. Adding
and deleting are off for the same reason; export the list if you need the data
elsewhere.

The attachment is linked through the permission-checked private view, never from
``MEDIA_URL``.
"""

from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin

from apps.contact.models import ContactSubmission


@admin.register(ContactSubmission)
class ContactSubmissionAdmin(ModelAdmin):
    """Submissions received through the contact form."""

    list_display = [
        "full_name",
        "email",
{%- if cookiecutter.countries_app != "none" %}
        "country_display_name",
{%- endif %}
        "enquiry_type",
        "subject",
        "submitted_at",
    ]
    list_filter = [
        "enquiry_type",
        "submitted_at",
{%- if cookiecutter.countries_app != "none" %}
        "country",
{%- endif %}
{%- if cookiecutter.stack == "wagtail" and cookiecutter.multisite == "multi" %}
        "site",
{%- endif %}
    ]
    search_fields = ["full_name", "email", "company_name", "subject", "message"]
    date_hierarchy = "submitted_at"
    list_per_page = 50
    ordering = ["-submitted_at"]
    fieldsets = [
        (
            _("Sender"),
            {"fields": ["full_name", "company_name", "email", "phone"]},
        ),
        (
            _("Enquiry"),
            {
                "fields": [
{%- if cookiecutter.countries_app != "none" %}
                    "country",
{%- endif %}
                    "enquiry_type",
                    "subject",
                    "message",
                    "attachment_link",
                    "submitted_at",
{%- if cookiecutter.stack == "wagtail" and cookiecutter.multisite == "multi" %}
                    "site",
{%- endif %}
                ]
            },
        ),
    ]

{%- if cookiecutter.countries_app != "none" %}

    @admin.display(description=_("Country"), ordering="country")
    def country_display_name(self, obj):
        """The country as a person reads it, whatever the backend stores.

        ``ordering`` still points at the real column, so the header stays
        sortable - by stored value, which is the only thing the database can sort.
        """
        return obj.country_name or "-"
{%- endif %}

    @admin.display(description=_("Attachment"))
    def attachment_link(self, obj):
        """A link through the permission-checked private view.

        Not ``obj.attachment.url``: private storage refuses to produce one,
        because a URL under ``MEDIA_URL`` hands the file to anyone who has the
        link, and an attachment on a contact form is personal data.
        """
        if not obj.attachment:
            return "-"
        return format_html(
            '<a href="{}" rel="noopener noreferrer">{}</a>',
            obj.attachment_download_url,
            obj.attachment_original_name or obj.attachment.name,
        )

    def get_readonly_fields(self, request, obj=None):
        # Every concrete field, plus the link. Computed rather than listed so a
        # field added to the model later cannot become editable by omission.
        return [field.name for field in self.model._meta.fields] + ["attachment_link"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        # With the view permission granted, Django still renders the detail page -
        # without a save button. That is exactly the surface wanted here.
        return False

    def has_delete_permission(self, request, obj=None):
        return False
