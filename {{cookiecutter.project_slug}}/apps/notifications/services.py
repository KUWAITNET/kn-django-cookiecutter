"""Rendering and delivery of the admin-editable notifications.

Everything leaves through ``send_notification``. It goes out with
``django.core.mail``, which this project points at django-post-office, so every
message - delivered or failed - is recorded and visible in the admin e-mail log
without this module knowing anything about it.
"""

import logging
from collections import defaultdict

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import mail
from django.template import engines
from django.template.exceptions import TemplateSyntaxError
from django.utils import translation
from django.utils.translation import get_language
{%- if cookiecutter.stack == "wagtail" %}
from wagtail.users.models import UserProfile
{%- endif %}

from apps.notifications.defaults import get_default
from apps.notifications.models import NotificationRecipient, NotificationTemplate

logger = logging.getLogger(__name__)

# Bodies are plain text, so the engine must not HTML-escape the context: an
# address containing "&" is not an entity in a text/plain part. Wrapping the
# stored source keeps the project's configured engine (and its template
# libraries) instead of building a second, differently-configured one.
_AUTOESCAPE_OPEN = "{% raw %}{% autoescape off %}{% endraw %}"
_AUTOESCAPE_CLOSE = "{% raw %}{% endautoescape %}{% endraw %}"


def _compile(source: str):
    return engines["django"].from_string(f"{_AUTOESCAPE_OPEN}{source}{_AUTOESCAPE_CLOSE}")


def check_template_source(source: str) -> str | None:
    """Return a readable error for invalid template source, or ``None``.

    Used by ``NotificationTemplate.clean`` so a broken tag is a field error on
    the edit page rather than an exception in a visitor's request.
    """
    if not source:
        return None
    try:
        _compile(source)
    except TemplateSyntaxError as exc:
        return str(exc)
    return None


def render_source(source: str, context: dict) -> str:
    return _compile(source).render(context)


def get_template(trigger, language: str) -> NotificationTemplate | None:
    """The stored row for ``(trigger, language)``, falling back to the default language."""
    rows = {row.language: row for row in NotificationTemplate.objects.filter(trigger=trigger)}
    return rows.get(language) or rows.get(settings.LANGUAGE_CODE)


def render_notification(trigger, context: dict, language: str | None = None) -> tuple[str, str]:
    """Render ``(subject, body)`` for ``trigger`` in ``language``.

    Falls back to the built-in copy when no row exists yet, so a project that
    has not run ``seed_notifications`` still sends a real message. The
    reference implementation returned a placeholder subject and an empty body
    instead, which reached real recipients.
    """
    language = language or get_language() or settings.LANGUAGE_CODE
    row = get_template(trigger, language)
    if row is not None:
        subject_source, body_source = row.subject, row.body
    else:
        subject_source = get_default(trigger, language, "subject")
        body_source = get_default(trigger, language, "body")

    body = render_source(body_source, context)
    # The subject becomes a mail header. Context values are submitter-supplied,
    # so a newline in one would otherwise let a visitor inject headers.
    subject = " ".join(render_source(subject_source, context).split())
    return subject, body


def get_recipients(trigger) -> list[str]:
    """Configured staff recipients for ``trigger``, falling back to ``DEFAULT_ADMIN_EMAIL``."""
    row = NotificationRecipient.objects.filter(trigger=trigger).first()
    configured = row.as_list() if row is not None else []
    if configured:
        return configured
    return [
        address.strip()
        for address in (settings.DEFAULT_ADMIN_EMAIL or "").split(",")
        if address.strip()
    ]


def get_recipient_language(email: str) -> str:
    """The language ``email`` should be written in.

    An address with no account behind it (a shared inbox, an external
    consultant) gets whichever language is active for the request that
    triggered the notification.
    """
    user = get_user_model().objects.filter(email__iexact=email, is_active=True).first()
{%- if cookiecutter.stack == "wagtail" %}
    if user is not None:
        preferred = UserProfile.get_for_user(user).get_preferred_language()
        if preferred:
            return preferred
{%- else %}
    # A stock Django user has no language preference. A project that adds one
    # (a ``preferred_language`` field on the user or its profile) gets it here
    # without touching this module.
    preferred = getattr(user, "preferred_language", "") if user is not None else ""
    if preferred:
        return preferred
{%- endif %}
    return get_language() or settings.LANGUAGE_CODE


def send_notification(
    trigger,
    context,
    recipients=None,
    language: str | None = None,
    from_email: str | None = None,
    reply_to=None,
) -> int:
    """Send ``trigger`` to each recipient in that recipient's language.

    ``recipients`` defaults to the addresses configured for the trigger.
    ``context`` may be a dict or a callable returning one; pass a callable when
    it contains translated values, because ``get_FOO_display()`` and
    ``str(lazy)`` resolve eagerly and a dict built once outside the language
    override would freeze to whichever language was rendered first.

    Returns the number of messages handed to the backend. Never raises: a
    notification is a side effect of somebody's form submission, and a mail
    failure must not turn their successful submission into a 500. The failure
    is logged here and recorded by post-office.
    """
    try:
        return _send(trigger, context, recipients, language, from_email, reply_to)
    except Exception:
        logger.exception("Notification %s could not be sent", trigger)
        return 0


def _send(trigger, context, recipients, language, from_email, reply_to) -> int:
    addresses = list(recipients) if recipients else get_recipients(trigger)
    # dict.fromkeys de-duplicates while keeping the configured order.
    addresses = [address for address in dict.fromkeys(addresses) if address]
    if not addresses:
        logger.warning("Notification %s has no recipients configured", trigger)
        return 0

    by_language = defaultdict(list)
    for address in addresses:
        by_language[language or get_recipient_language(address)].append(address)

    messages = []
    for code, group in by_language.items():
        with translation.override(code):
            resolved_context = context() if callable(context) else dict(context)
            subject, body = render_notification(trigger, resolved_context, code)
            for address in group:
                # One message per address: recipients of the same notification
                # never see each other's addresses.
                messages.append(
                    mail.EmailMessage(
                        subject=subject,
                        body=body,
                        from_email=from_email or settings.DEFAULT_FROM_EMAIL,
                        to=[address],
                        reply_to=list(reply_to) if reply_to else None,
                    )
                )

    # One connection for the whole batch rather than one per message.
    connection = mail.get_connection()
    connection.send_messages(messages)
    return len(messages)
