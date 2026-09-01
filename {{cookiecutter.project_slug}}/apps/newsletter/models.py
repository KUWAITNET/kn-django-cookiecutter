"""Newsletter subscribers and the log of what was sent to them.

Double opt-in: subscribing records an address and mails a confirmation link;
nothing is ever sent to an address that has not used that link. This is why the
subscribe endpoint cannot be used to mail somebody repeatedly - and why it is
rate-limited and spam-protected on top (in the reference implementation it sent
an e-mail per unauthenticated request, with no limit at all).
"""

import uuid

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

#: Audience value meaning "every mailable subscriber, whatever their language".
AUDIENCE_ALL = "all"


def language_choices():
    """The project's configured languages, resolved at access time.

    A callable rather than ``settings.LANGUAGES`` itself: Django serialises a
    callable by reference, so adding a language does not produce a migration
    that only rewrites a choices list.
    """
    return list(settings.LANGUAGES)


def default_language():
    return settings.LANGUAGE_CODE


def absolute_url(path: str) -> str:
    """``path`` against ``BASE_URL``.

    Links in e-mail have no request to build against, and an unsubscribe link
    that only works from inside the site is not an unsubscribe link.
    """
    return f"{settings.BASE_URL.rstrip('/')}{path}"


class SubscriberQuerySet(models.QuerySet):
    def mailable(self):
        """Confirmed and still subscribed - the only addresses a campaign may reach."""
        return self.filter(is_confirmed=True, is_active=True)


class Subscriber(models.Model):
    email = models.EmailField(verbose_name=_("E-mail"))
{%- if cookiecutter.multisite == "multi" %}
    site = models.ForeignKey(
        "wagtailcore.Site",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name=_("Site"),
    )
{%- endif %}
    language = models.CharField(
        max_length=16,
        choices=language_choices,
        default=default_language,
        verbose_name=_("Language"),
        help_text=_("The language the site was in when they subscribed."),
    )
    is_confirmed = models.BooleanField(
        default=False,
        verbose_name=_("Confirmed"),
        help_text=_("Set when the address has been confirmed from the e-mail we sent."),
    )
    is_active = models.BooleanField(default=True, verbose_name=_("Subscribed"))
    # Unguessable rather than sequential: the unsubscribe link is the only
    # credential, and it has to work in one click without a login.
    token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Subscribed at"))
    confirmed_at = models.DateTimeField(null=True, blank=True, verbose_name=_("Confirmed at"))
    unsubscribed_at = models.DateTimeField(
        null=True, blank=True, verbose_name=_("Unsubscribed at")
    )

    objects = SubscriberQuerySet.as_manager()

    class Meta:
        constraints = [
{%- if cookiecutter.multisite == "multi" %}
            models.UniqueConstraint(
                fields=["email", "site"], name="newsletter_unique_subscriber_per_site"
            ),
            # NULLs do not collide in PostgreSQL, so the constraint above would
            # let the same address in twice while no site is recorded.
            models.UniqueConstraint(
                fields=["email"],
                condition=models.Q(site__isnull=True),
                name="newsletter_unique_subscriber_without_site",
            ),
{%- else %}
            models.UniqueConstraint(fields=["email"], name="newsletter_unique_subscriber"),
{%- endif %}
        ]
        ordering = ["-created_at"]
        verbose_name = _("Subscriber")
        verbose_name_plural = _("Subscribers")

    def __str__(self):
        return self.email

    @property
    def confirm_url(self) -> str:
        return absolute_url(reverse("newsletter:confirm", args=[self.token]))

    @property
    def unsubscribe_url(self) -> str:
        return absolute_url(reverse("newsletter:unsubscribe", args=[self.token]))


class Campaign(models.Model):
    """What was sent, to how many people, by whom.

    Written after the send, never before: there is no draft or schedule step, so
    a row here always means messages left the building. Copy is kept per
    language in one JSON column rather than in a column pair per language, so
    adding a language to the project does not need a migration here.
    """

    content = models.JSONField(
        default=dict,
        verbose_name=_("Content"),
        help_text=_("Subject and body per language code."),
    )
    audience = models.CharField(max_length=32, default=AUDIENCE_ALL, verbose_name=_("Audience"))
    recipient_count = models.PositiveIntegerField(default=0, verbose_name=_("Recipients"))
    sent_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Sent at"))
    sent_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name=_("Sent by"),
    )

    class Meta:
        ordering = ["-sent_at"]
        verbose_name = _("Campaign")
        verbose_name_plural = _("Campaigns")

    def __str__(self):
        return self.subject or str(_("Newsletter"))

    @property
    def subject(self) -> str:
        """The default language's subject, or the first one composed."""
        content = self.content or {}
        entry = content.get(settings.LANGUAGE_CODE)
        if entry is None and content:
            entry = next(iter(content.values()))
        return (entry or {}).get("subject", "")
