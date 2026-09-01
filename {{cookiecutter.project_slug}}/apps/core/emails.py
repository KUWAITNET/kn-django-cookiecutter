"""Branded HTML e-mail, used by every outbound message in the project.

Nothing calls ``django.core.mail.send_mail`` directly. Everything goes through
``send_branded_mail``/``build_branded_email``, so every message carries the site's
branding, a plain-text alternative, absolute URLs, and the right text direction.

Transport is ``django.core.mail`` as usual - which is django-post-office, wired in
settings. That is transparent here on purpose: post-office logs and retries every
send, and no call site has to know it exists.
"""

import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives, get_connection
from django.utils import timezone
from django.utils.html import strip_tags
from django.utils.safestring import mark_safe
from django.utils.translation import get_language_bidi

from apps.core.utils import absolute_url

logger = logging.getLogger("{{ cookiecutter.project_slug }}")

#: Static path of the logo shown in the e-mail header. Missing is fine: the
#: template falls back to a text wordmark.
EMAIL_LOGO_STATIC_PATH = "img/email-logo.png"

EMAIL_TEMPLATE = "emails/base_email.html"

#: ``emails/base_email.html`` is a *shell* with a ``content`` block, so that
#: hand-written messages can extend it. This one-line child fills that block from
#: a body the caller supplies as text or HTML. It is a string rather than another
#: template file so that a caller with one paragraph to send does not have to add
#: a template to the project first.
_BODY_TEMPLATE_SOURCE = """{% raw %}{% extends "emails/base_email.html" %}
{% block content %}{% if body_html %}{{ body_html }}{% else %}{% for line in body_lines %}{% if line %}<p style="margin:0 0 12px;">{{ line }}</p>{% else %}<div style="height:8px; line-height:8px; font-size:0;">&nbsp;</div>{% endif %}{% endfor %}{% endif %}{% endblock %}{% endraw %}"""

_body_template = None


def _get_body_template():
    """Compile the child template once, on first use rather than at import."""
    global _body_template
    if _body_template is None:
        from django.template import engines

        _body_template = engines["django"].from_string(_BODY_TEMPLATE_SOURCE)
    return _body_template


def _logo_url() -> str:
    """Absolute URL of the branding logo, or "" when it is not collected.

    ``static()`` is called here rather than at import time: under a hashed
    manifest storage it raises for a file that has not been collected yet, and an
    import-time failure would take the whole project down instead of one image.
    """
    from django.templatetags.static import static

    try:
        return absolute_url(static(EMAIL_LOGO_STATIC_PATH))
    except ValueError:
        return ""


def render_branded_email(subject, body_text=None, body_html=None, context=None) -> str:
    """Render a body inside the shared HTML shell.

    Pass exactly one of ``body_text`` (plain text, wrapped into paragraphs) or
    ``body_html``. ``body_html`` is marked safe, so it must come from trusted
    markup - an admin-composed rich-text body from a restricted feature set, or a
    ``format_html``-built summary. Never pass raw visitor input.

    ``context`` overrides or adds shell values: ``preheader``, ``footer_note``,
    ``unsubscribe_url``, ``logo_width``, ``logo_height``.
    """
    render_context = {
        "subject": subject,
        "body_lines": body_text.splitlines() if body_text is not None else None,
        "body_html": mark_safe(body_html) if body_html is not None else None,  # noqa: S308
        "logo_url": _logo_url(),
        "base_url": settings.BASE_URL,
        "site_name": settings.SITE_NAME,
        "client_name": settings.CLIENT_NAME,
        "year": timezone.now().year,
        # The shell reads the direction from the active language itself; this is
        # here for messages that need it in their own markup. Callers wrap the
        # call in translation.override() to send in the recipient's language
        # rather than the server's.
        "is_rtl": get_language_bidi(),
    }
    render_context.update(context or {})
    return _get_body_template().render(render_context)


def build_branded_email(
    subject,
    recipient_list,
    body_text=None,
    body_html=None,
    from_email=None,
    context=None,
    connection=None,
) -> EmailMultiAlternatives:
    """Build, but do not send, a branded message.

    Separate from sending so a campaign can build many messages and push them
    over one connection.
    """
    plain_text = body_text if body_text is not None else strip_tags(body_html or "").strip()
    message = EmailMultiAlternatives(
        subject=str(subject),
        body=plain_text,
        from_email=from_email or settings.DEFAULT_FROM_EMAIL,
        to=list(recipient_list or []),
        connection=connection,
    )
    message.attach_alternative(
        render_branded_email(subject, body_text=body_text, body_html=body_html, context=context),
        "text/html",
    )
    return message


def send_branded_mail(
    subject,
    recipient_list,
    body_text=None,
    body_html=None,
    from_email=None,
    context=None,
) -> int:
    """Send one branded message. Returns the number of messages sent.

    A delivery failure is logged, not raised: a visitor who filled in a contact
    form should not see a 500 because SMTP was briefly unreachable, and the send
    is recorded in the post-office log either way.
    """
    if not recipient_list:
        return 0
    message = build_branded_email(
        subject,
        recipient_list,
        body_text=body_text,
        body_html=body_html,
        from_email=from_email,
        context=context,
    )
    try:
        return message.send(fail_silently=False)
    except Exception:
        logger.exception("Branded e-mail failed: subject=%r", str(subject))
        return 0


def send_branded_mass_mail(messages) -> int:
    """Send pre-built messages over a single connection."""
    connection = get_connection()
    try:
        return connection.send_messages(list(messages)) or 0
    except Exception:
        logger.exception("Bulk branded e-mail failed")
        return 0
