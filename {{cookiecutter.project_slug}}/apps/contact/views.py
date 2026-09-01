"""POST handling for the contact form, and the AJAX contract every form speaks.

``handle_contact_post`` is the whole submission path{% if cookiecutter.stack == "wagtail" %}, shared by ``ContactPage.serve()``
and any other page that wants the same form{% endif %}. Keeping it here rather than in the
view means the rate limit, the AJAX contract and the notification cannot drift
apart between two callers - which is exactly how the reference project ended up
with six near-identical ``serve()`` overrides that behaved differently.

The AJAX contract, which the JavaScript in ``contact/contact_page.html`` and every
future form template rely on:

===========================  ======  =========================================
case                         status  body
===========================  ======  =========================================
valid, XHR                   200     ``{"ok": true}``
invalid, XHR                 400     ``{"ok": false, "errors": {field: [...]}}``
rate limited, XHR            429     ``{"ok": false, "errors": {...}}``
valid, no XHR                200     page re-render, ``submitted`` is true
invalid, no XHR              200     page re-render with the bound form
===========================  ======  =========================================
"""

import logging
from typing import NamedTuple

from django.conf import settings
from django.http import HttpResponse, JsonResponse
{%- if cookiecutter.stack == "django" and cookiecutter.frontend != "api_only" %}
from django.shortcuts import render
{%- endif %}
from django.utils.html import format_html, format_html_join
from django.utils.translation import gettext
from django.utils.translation import gettext_lazy as _
{%- if cookiecutter.rate_limiting == "yes" and cookiecutter.frontend != "api_only" %}
from django_ratelimit.core import is_ratelimited
{%- endif %}
{%- if cookiecutter.stack == "wagtail" and cookiecutter.multisite == "multi" %}
from wagtail.models import Site
{%- endif %}

from apps.contact.forms import ContactForm
from apps.core.emails import send_branded_mail
from apps.core.utils import ltr_isolate

logger = logging.getLogger("{{ cookiecutter.project_slug }}")

TEMPLATE_NAME = "contact/contact_page.html"

RATE_LIMIT_MESSAGE = _(
    "Too many submissions from this address. Please try again in a little while."
)


class SubmissionResult(NamedTuple):
    """What ``handle_contact_post`` decided.

    ``response`` is not ``None`` when the request is already finished (the AJAX
    paths); otherwise the caller renders the page itself with ``form``,
    ``submitted`` and ``status``.
    """

    response: HttpResponse | None
    form: ContactForm
    submitted: bool
    status: int = 200


def is_ajax(request) -> bool:
    """Whether the browser asked for the JSON contract rather than a page."""
    return request.headers.get("X-Requested-With") == "XMLHttpRequest"
{% if cookiecutter.rate_limiting == "yes" and cookiecutter.frontend != "api_only" %}

def _rate_limited(request) -> bool:
    """Whether this client has spent its submission budget.

    ``is_ratelimited`` rather than the ``@ratelimit`` decorator because the same
    check has to run from a page's ``serve(self, request, ...)``, where a
    decorator would read ``self`` as the request.

    The budget is per IP and deliberately small: every submission costs an
    outbound e-mail and a row someone has to read.
    """
    return is_ratelimited(
        request=request,
        group="contact:submit",
        key="ip",
        rate=settings.RATELIMIT_FORM_SUBMIT,
        method="POST",
        increment=True,
    )
{% endif %}

def handle_contact_post(request, page=None) -> SubmissionResult:
    """Validate, store and notify. Never renders."""
{%- if cookiecutter.rate_limiting == "yes" and cookiecutter.frontend != "api_only" %}
    if _rate_limited(request):
        form = ContactForm(request=request)
        form.add_error(None, RATE_LIMIT_MESSAGE)
        if is_ajax(request):
            return SubmissionResult(
                JsonResponse({"ok": False, "errors": form.errors}, status=429),
                form,
                False,
                429,
            )
        return SubmissionResult(None, form, False, 429)
{%- endif %}

    form = ContactForm(request.POST, request.FILES, request=request)
    if not form.is_valid():
        if is_ajax(request):
            # form.errors is an ErrorDict of ErrorLists, both of which JSON-encode
            # as {field: [message, ...]} - which is what the client indexes by
            # input name to place each message.
            return SubmissionResult(
                JsonResponse({"ok": False, "errors": form.errors}, status=400), form, False, 400
            )
        return SubmissionResult(None, form, False)

    submission = form.save(commit=False)
{%- if cookiecutter.stack == "wagtail" and cookiecutter.multisite == "multi" %}
    # The one line that makes a submission multi-tenant. Never a form field.
    submission.site = Site.find_for_request(request)
{%- endif %}
    submission.save()
    send_contact_notification(submission, page=page)

    # A fresh form: re-rendering the bound one after a successful save shows the
    # visitor their message still sitting in the box, which reads as a failure.
    return SubmissionResult(
        JsonResponse({"ok": True}) if is_ajax(request) else None,
        ContactForm(request=request),
        True,
    )


# --- Notification -------------------------------------------------------------


def notification_recipients(page=None) -> list[str]:
    """Who is told about a new submission.

    The page's own address wins so an editor can redirect enquiries without a
    deploy; ``DEFAULT_ADMIN_EMAIL`` is the fallback. Both accept a comma-separated
    list.
    """
    configured = getattr(page, "notification_email", "") or settings.DEFAULT_ADMIN_EMAIL
    return [address.strip() for address in str(configured).split(",") if address.strip()]


def notification_context(submission) -> dict:
    """The submission as e-mail template variables."""
    return {
        "name": submission.full_name,
        "company": submission.company_name,
        "email": submission.email,
        # Isolated so a "+965..." number does not get reordered by the
        # bidirectional algorithm inside an Arabic paragraph.
        "phone": ltr_isolate(str(submission.phone)) if submission.phone else "",
{%- if cookiecutter.countries_app == "yes" %}
        "country": submission.country.localized_name,
{%- endif %}
        "type": submission.get_enquiry_type_display(),
        "subject": submission.subject,
        "message": submission.message,
        "attachment": submission.attachment_original_name,
    }


def _render_notification(submission):
    """``(subject, body_html)`` for the staff notification.
{% if cookiecutter.notifications_app == "yes" %}
    Prefers the admin-editable template so the wording is an editor's decision.
    The import is guarded rather than assumed: this app must keep working if the
    notifications app is removed from the project later.
{%- else %}
    Built here, from a template, because this project has no notifications app.
{%- endif %}
    """
    context = notification_context(submission)
{%- if cookiecutter.notifications_app == "yes" %}

    try:
        from apps.notifications.models import NotificationTrigger, RecipientType
        from apps.notifications.services import render_notification_template

        return render_notification_template(
            NotificationTrigger.CONTACT_SUBMISSION,
            RecipientType.ADMIN,
            context=context,
        )
    except (ImportError, AttributeError, LookupError):
        logger.info("No admin-editable contact template; using the built-in body.")
{%- endif %}

    subject = gettext("New contact enquiry: %(subject)s") % {"subject": submission.subject}
    rows = [
        (_("Name"), context["name"]),
        (_("Company"), context["company"]),
        (_("E-mail"), context["email"]),
        (_("Phone"), context["phone"]),
{%- if cookiecutter.countries_app == "yes" %}
        (_("Country"), context["country"]),
{%- endif %}
        (_("Type"), context["type"]),
        (_("Subject"), context["subject"]),
        (_("Attachment"), context["attachment"]),
    ]
    body_html = format_html(
        "<dl>{}</dl><p><strong>{}</strong></p><p>{}</p>",
        format_html_join(
            "", "<dt>{}</dt><dd>{}</dd>", ((label, value) for label, value in rows if value)
        ),
        _("Message"),
        context["message"],
    )
    return subject, body_html


def send_contact_notification(submission, page=None) -> None:
    """Tell staff about a new submission.

    Failures are logged, not raised: the visitor's message is already stored, and
    a mail-server outage must not turn a successful submission into a 500 that
    invites them to send it again.
    """
    recipients = notification_recipients(page)
    if not recipients:
        logger.warning("Contact submission %s stored with no notification recipient", submission.pk)
        return
    subject, body_html = _render_notification(submission)
    send_branded_mail(subject, recipients, body_html=body_html)
{% if cookiecutter.stack == "django" and cookiecutter.frontend != "api_only" %}

# --- The page -----------------------------------------------------------------


def contact(request):
    """The contact page. GET renders the form; POST goes through the shared path."""
    if request.method != "POST":
        return render(
            request,
            TEMPLATE_NAME,
            {"form": ContactForm(request=request), "submitted": False},
        )

    result = handle_contact_post(request)
    if result.response is not None:
        return result.response
    return render(
        request,
        TEMPLATE_NAME,
        {"form": result.form, "submitted": result.submitted},
        status=result.status,
    )
{%- endif %}
