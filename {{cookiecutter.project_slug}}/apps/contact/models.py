"""The reference public form, end to end.

Copy this app to add another form. It is the shape every KUWAITNET public form
takes: a submission model that only the form writes, an explicit ``ModelForm``
with server-side validation and bot protection, a rate-limited view that speaks
one AJAX contract, an attachment that is validated and stored privately, and a
read-only admin - because a submission an administrator can edit is no longer
evidence of what the visitor sent.
{% if cookiecutter.stack == "wagtail" %}
``ContactPage`` owns the copy (intro, thank-you text, notification recipient) so
an editor changes it without a deploy, and handles POST in ``serve()`` rather
than through the CMS form builder, which cannot express a validated split-phone
field or a private attachment.
{%- endif %}
"""

{%- if cookiecutter.stack == "wagtail" %}

from django.core.validators import validate_email
from django.db import models
from django.template.response import TemplateResponse
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _
from phonenumber_field.modelfields import PhoneNumberField
from wagtail.admin.panels import FieldPanel, MultiFieldPanel
from wagtail.fields import RichTextField
from wagtail.rich_text import expand_db_html

from apps.core.models import BasePage{% if cookiecutter.multisite == "multi" %}, SiteScopedModel{% endif %}
from apps.core.validators import SecureFileField
{%- else %}

from django.db import models
from django.utils.translation import gettext_lazy as _
from phonenumber_field.modelfields import PhoneNumberField

from apps.core.validators import SecureFileField
{%- endif %}

#: The narrowest set that still lets someone attach a specification or a quote.
#: An allowlist, never a denylist: a denylist is a guess about what is dangerous
#: and the guess is always incomplete.
#:
#: Documents only. Adding "png"/"jpg" here would produce a field that is neither
#: a document field nor an image field: images have to be re-encoded server-side
#: to strip EXIF and embedded payloads, and that is what ``SecureImageField``
#: does. A form that genuinely needs a photo declares a second, image-only field.
ATTACHMENT_EXTENSIONS = ("pdf", "doc", "docx")

#: Below the 10 MB request-body cap, so an oversized upload is refused by this
#: field's own message rather than by a bare 413 from the server.
ATTACHMENT_MAX_MB = 5

{%- if cookiecutter.stack == "wagtail" %}

#: Rich-text features an editor needs for form copy. Deliberately narrow: this
#: text is rendered into the page and into an e-mail, and images and embeds do
#: not survive the e-mail.
FORM_COPY_FEATURES = ["bold", "italic", "link", "ol", "ul"]


def validate_email_list(value):
    """Validate a comma-separated list of e-mail addresses.

    A module-level function so a migration can serialise it by reference.
    """
    for address in str(value or "").split(","):
        if address.strip():
            validate_email(address.strip())
{%- endif %}


class ContactSubmission({% if cookiecutter.stack == "wagtail" and cookiecutter.multisite == "multi" %}SiteScopedModel{% else %}models.Model{% endif %}):
    """One message sent through the contact form.

    Written by ``apps.contact.forms.ContactForm`` and by nothing else. The admin
    is read-only, so a row here is a faithful record of what was submitted.
    """

    class EnquiryType(models.TextChoices):
        GENERAL = "general", _("General enquiry")
        SALES = "sales", _("Sales")
        SUPPORT = "support", _("Support")
        CAREERS = "careers", _("Careers")
        OTHER = "other", _("Other")

    full_name = models.CharField(_("full name"), max_length=255)
    company_name = models.CharField(_("company name"), max_length=255, blank=True)
    email = models.EmailField(_("e-mail"))
    # Stored in E.164. The form builds it from a country-code select plus a
    # national number and validates it with phonenumbers; see forms.py.
    phone = PhoneNumberField(_("phone"), blank=True)
{%- if cookiecutter.countries_app == "yes" %}
    country = models.ForeignKey(
        "cities.Country",
        # A submission must never lose its country because a reference row was
        # deleted; the country admin deactivates rather than deletes for the same
        # reason.
        on_delete=models.PROTECT,
        # Nothing ever walks back from a country to its enquiries.
        related_name="+",
        verbose_name=_("country"),
    )
{%- endif %}
    enquiry_type = models.CharField(
        _("type of enquiry"),
        max_length=20,
        choices=EnquiryType.choices,
        db_index=True,
    )
    subject = models.CharField(_("subject"), max_length=255)
    message = models.TextField(_("message"))
    # private=True routes this to PRIVATE_MEDIA_ROOT and gives it a generated
    # filename: an attachment on a contact form is personal data, and under
    # MEDIA_ROOT it would be a public document reachable by guessing a name.
    attachment = SecureFileField(
        _("attachment"),
        blank=True,
        extensions=ATTACHMENT_EXTENSIONS,
        max_mb=ATTACHMENT_MAX_MB,
        private=True,
    )
    attachment_original_name = models.CharField(
        _("attachment file name"),
        max_length=255,
        blank=True,
        # Display only. The name on disk is a UUID; showing the visitor's own
        # filename back to staff is useful, trusting it is not.
        help_text=_("The name the visitor's file had. Never used on disk."),
    )
    submitted_at = models.DateTimeField(_("submitted at"), auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-submitted_at"]
        verbose_name = _("contact submission")
        verbose_name_plural = _("contact submissions")

    def __str__(self):
        when = f"{self.submitted_at:%Y-%m-%d}" if self.submitted_at else "-"
        return f"{self.full_name} - {self.get_enquiry_type_display()} ({when})"

    @property
    def attachment_download_url(self) -> str:
        """Permission-checked download URL, or "" when there is no attachment.

        Never ``attachment.url``: private storage refuses to produce one, because
        a URL under ``MEDIA_URL`` would serve this file to anybody who has the
        link. ``apps.core.views.serve_private_file`` checks
        ``core.access_private_media`` first.
        """
        from django.urls import reverse

        if not self.attachment:
            return ""
        return reverse("private_media", kwargs={"relative_path": self.attachment.name})
{%- if cookiecutter.stack == "wagtail" %}


class ContactPage(BasePage):
    """Contact page: editor-owned copy around a hand-written form.

    Not a Wagtail form-builder page. The form needs a validated split-phone
    field, a private attachment and a spam-protection mixin, none of which the
    form builder can express, so the form is a plain ``ModelForm`` and ``serve()``
    handles the POST.
    """

    intro = RichTextField(
        _("introduction"),
        blank=True,
        features=FORM_COPY_FEATURES,
        help_text=_("Shown above the form."),
    )
    thank_you_text = RichTextField(
        _("thank-you text"),
        blank=True,
        features=FORM_COPY_FEATURES,
        help_text=_("Shown after a successful submission."),
    )
    notification_email = models.CharField(
        _("notification e-mail"),
        max_length=500,
        blank=True,
        # A list, not one address, so an editor can add a second inbox without a
        # deploy - which is why this is a CharField with its own validator rather
        # than an EmailField.
        validators=[validate_email_list],
        help_text=_(
            "Where submissions are sent. Separate several addresses with commas. "
            "Leave blank to use the project default."
        ),
    )

    content_panels = BasePage.content_panels + [
        FieldPanel("intro"),
        FieldPanel("thank_you_text"),
        MultiFieldPanel([FieldPanel("notification_email")], heading=_("Notifications")),
    ]

    template = "contact/contact_page.html"
    max_count = 1

    class Meta:
        verbose_name = _("contact page")

    def get_context(self, request, *args, **kwargs):
        from apps.contact.forms import ContactForm

        context = super().get_context(request, *args, **kwargs)
        # An unbound form for GET. serve() replaces it with the bound one on POST.
        context["form"] = ContactForm(request=request)
        context["submitted"] = False
        context["submit_error"] = ""
        # Rich text is expanded here instead of with the |richtext filter, so the
        # template stays a plain Django template that either stack can render and
        # needs no CMS tag library. Admin-authored markup from a restricted
        # feature set, so marking it safe is the same trust the filter applies.
        context["intro_html"] = mark_safe(expand_db_html(self.intro))  # noqa: S308
        context["thank_you_html"] = mark_safe(expand_db_html(self.thank_you_text))  # noqa: S308
        return context

    def serve(self, request, *args, **kwargs):
        # Imported inside the method: forms imports models, so a module-level
        # import here is a cycle.
        from apps.contact.views import handle_contact_post

        if request.method != "POST":
            return super().serve(request, *args, **kwargs)

        result = handle_contact_post(request, page=self)
        if result.response is not None:
            return result.response

        context = self.get_context(request, *args, **kwargs)
        context["form"] = result.form
        context["submitted"] = result.submitted
        context["submit_error"] = result.submit_error
        return TemplateResponse(request, self.get_template(request), context, status=result.status)
{%- endif %}
