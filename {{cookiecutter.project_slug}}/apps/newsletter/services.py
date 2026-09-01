"""Subscribing, confirming, unsubscribing and sending.

Messages are built by ``apps.core.emails`` so a newsletter looks like every other
e-mail the project sends, and go out over ``django.core.mail`` - which is
django-post-office here, so each one is recorded and visible in the admin e-mail
log without this module knowing about it.
"""

import logging

from django.conf import settings
from django.db.models import Count
from django.template import engines
from django.template.exceptions import TemplateSyntaxError
from django.utils import timezone, translation
from django.utils.html import format_html
from django.utils.translation import gettext as _

from apps.core.emails import build_branded_email, send_branded_mass_mail
from apps.newsletter.models import AUDIENCE_ALL, Campaign, Subscriber
{% if cookiecutter.notifications_app == "yes" %}from apps.notifications.models import NotificationTrigger, RecipientType
from apps.notifications.services import render_notification_template
{% endif %}
logger = logging.getLogger(__name__)

# A subject is a header, not markup, so it is rendered with escaping off - an
# ampersand in a site name must not arrive as "&amp;". Bodies keep Django's
# autoescaping: they are HTML fragments, and the values dropped into them are
# addresses a visitor typed.
_AUTOESCAPE_OPEN = "{% raw %}{% autoescape off %}{% endraw %}"
_AUTOESCAPE_CLOSE = "{% raw %}{% endautoescape %}{% endraw %}"


def _compile(source: str, autoescape: bool = True):
    if not autoescape:
        source = f"{_AUTOESCAPE_OPEN}{source}{_AUTOESCAPE_CLOSE}"
    return engines["django"].from_string(source)


def check_template_source(source: str) -> str | None:
    """Return a readable error for invalid template source, or ``None``.

    Campaign copy is compiled while it is being composed, so a broken tag is a
    field error in the admin rather than a half-sent campaign.
    """
    if not source:
        return None
    try:
        _compile(source)
    except TemplateSyntaxError as exc:
        return str(exc)
    return None


def render_source(source: str, context: dict, autoescape: bool = True) -> str:
    return _compile(source, autoescape=autoescape).render(context)


def _build_message(subject: str, body_html: str, subscriber: Subscriber):
    message = build_branded_email(
        # Collapsed to one line: the subject becomes a mail header, and a
        # newline in a rendered value must not be able to start a header.
        " ".join(subject.split()),
        [subscriber.email],
        body_html=body_html,
    )
    message.extra_headers.update(
        {
            # One-click unsubscribe (RFC 8058): mail clients show a real button
            # instead of the recipient reaching for "report as spam".
            "List-Unsubscribe": f"<{subscriber.unsubscribe_url}>",
            "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
        }
    )
    return message


def _mail_context(subscriber: Subscriber) -> dict:
    return {
        "email": subscriber.email,
        "site_name": settings.SITE_NAME,
        "confirm_url": subscriber.confirm_url,
        "unsubscribe_url": subscriber.unsubscribe_url,
    }


def subscribe(email: str, language: str | None = None, site=None) -> tuple[Subscriber, bool]:
    """Record ``email``, or bring a previously unsubscribed address back.

    Idempotent on purpose: re-submitting an address is never an error, it just
    ends up subscribed again. An address that already confirmed keeps its
    confirmation, so unsubscribing and resubscribing does not put somebody
    through confirmation twice.
    """
    lookup = {"email": email}
{%- if cookiecutter.multisite == "multi" %}
    lookup["site"] = site
{%- endif %}
    subscriber, created = Subscriber.objects.get_or_create(
        defaults={"language": language or settings.LANGUAGE_CODE}, **lookup
    )
    subscriber.language = language or subscriber.language
    subscriber.is_active = True
    subscriber.unsubscribed_at = None
    subscriber.save(update_fields=["language", "is_active", "unsubscribed_at"])
    return subscriber, created


def send_confirmation(subscriber: Subscriber) -> bool:
    """Mail ``subscriber`` the link that activates their subscription.

    Returns whether a message was handed to the backend. Never raises: a mail
    outage must not turn a working form into a 500.
    """
    try:
        with translation.override(subscriber.language):
            context = _mail_context(subscriber)
{%- if cookiecutter.notifications_app == "yes" %}
            subject, body_html = render_notification_template(
                NotificationTrigger.NEWSLETTER_SUBSCRIPTION,
                RecipientType.USER,
                context=context,
                language=subscriber.language,
            )
{%- else %}
            subject = _("Confirm your newsletter subscription")
            body_html = format_html(
                '<p>{}</p>\n<p><a href="{}">{}</a></p>\n<p>{}</p>',
                _("%(email)s was used to subscribe to the %(site)s newsletter.")
                % {"email": context["email"], "site": context["site_name"]},
                context["confirm_url"],
                _("Confirm the subscription"),
                _(
                    "If this was not you, ignore this message. Nothing will be sent "
                    "unless the link above is used."
                ),
            )
{%- endif %}
            message = _build_message(subject, body_html, subscriber)
        send_branded_mass_mail([message])
    except Exception:
        logger.exception("Newsletter confirmation to subscriber %s failed", subscriber.pk)
        return False
    return True


def confirm(token) -> Subscriber | None:
    """Activate the subscription behind ``token``; ``None`` if there is none."""
    subscriber = Subscriber.objects.filter(token=token).first()
    if subscriber is None:
        return None
    if not subscriber.is_confirmed or not subscriber.is_active:
        subscriber.is_confirmed = True
        subscriber.is_active = True
        subscriber.confirmed_at = subscriber.confirmed_at or timezone.now()
        subscriber.unsubscribed_at = None
        subscriber.save(
            update_fields=["is_confirmed", "is_active", "confirmed_at", "unsubscribed_at"]
        )
    return subscriber


def unsubscribe(token) -> Subscriber | None:
    """Stop mailing the subscriber behind ``token``; ``None`` if there is none.

    Safe to call again: following the link a second time shows the same page and
    leaves the original ``unsubscribed_at`` alone. Mail clients prefetch links,
    so this endpoint has to be idempotent rather than a state machine.
    """
    subscriber = Subscriber.objects.filter(token=token).first()
    if subscriber is None:
        return None
    if subscriber.is_active:
        subscriber.is_active = False
        subscriber.unsubscribed_at = timezone.now()
        subscriber.save(update_fields=["is_active", "unsubscribed_at"])
    return subscriber


def subscribers_for(audience: str):
    """The mailable subscribers an audience selector resolves to."""
    queryset = Subscriber.objects.mailable()
    if audience and audience != AUDIENCE_ALL:
        queryset = queryset.filter(language=audience)
    return queryset.order_by("pk")


def recipient_counts() -> dict[str, int]:
    """How many subscribers each audience option would reach right now."""
    counts = {code: 0 for code, _label in settings.LANGUAGES}
    for row in Subscriber.objects.mailable().values("language").annotate(total=Count("pk")):
        counts[row["language"]] = counts.get(row["language"], 0) + row["total"]
    counts[AUDIENCE_ALL] = sum(counts.values())
    return counts


def send_campaign(content: dict, audience: str = AUDIENCE_ALL, sent_by=None) -> Campaign:
    """Send one message per subscriber in that subscriber's language, then log it.

    ``content`` maps a language code to ``{"subject": ..., "body": ...}``. A
    language nobody composed falls back to the default language and then to
    whatever was composed, so no subscriber is silently skipped. The guard on an
    empty ``content`` is deliberate: the reference implementation relied on its
    form having validated that, and raised StopIteration when called any other
    way.
    """
    if not content:
        raise ValueError("A campaign needs copy in at least one language")

    fallback = content.get(settings.LANGUAGE_CODE) or next(iter(content.values()))

    messages = []
    for subscriber in subscribers_for(audience):
        entry = content.get(subscriber.language) or fallback
        with translation.override(subscriber.language):
            # Rendered inside the override so the body, the branded shell's text
            # direction and the appended unsubscribe line agree on one language.
            context = _mail_context(subscriber)
            subject = render_source(entry["subject"], context, autoescape=False)
            body_html = render_source(entry["body"], context)
            footer = format_html(
                '<p><a href="{}">{}</a></p>',
                subscriber.unsubscribe_url,
                _("Unsubscribe from this newsletter"),
            )
            messages.append(_build_message(subject, f"{body_html}\n{footer}", subscriber))

    # One connection for the whole campaign rather than a handshake per
    # recipient, and one message per recipient rather than a shared To.
    send_branded_mass_mail(messages)

    return Campaign.objects.create(
        content=content,
        audience=audience,
        recipient_count=len(messages),
        sent_by=sent_by if sent_by is not None and sent_by.is_authenticated else None,
    )
