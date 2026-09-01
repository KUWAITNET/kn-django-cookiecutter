"""Admin-editable transactional e-mail: one row per trigger per language.

The coupling surface between the rest of the project and this app is a single
string - the ``NotificationTrigger`` value. Recipients and copy are data an
editor owns, not code, so adding a form or changing an e-mail's wording is not
a deployment.

Copy is stored as Django template source and rendered with the Django template
engine (see ``apps.notifications.services``). Invalid syntax is rejected on
save with a field error, never at send time, because a template that only
fails when a visitor submits a form is a bug the client discovers first.
"""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.notifications.defaults import get_default

#: Fields the admin can restore to their built-in value one at a time. Also the
#: allowlist for the reset view, whose field name comes from the URL.
RESETTABLE_FIELDS = ("subject", "body")


def language_choices():
    """The project's configured languages, resolved at access time.

    A callable rather than ``settings.LANGUAGES`` itself: Django serialises a
    callable by reference, so adding a language does not produce a migration
    that only rewrites a choices list.
    """
    return list(settings.LANGUAGES)


def _split_addresses(value: str) -> list[str]:
    return [address.strip() for address in (value or "").split(",") if address.strip()]


class NotificationTrigger(models.TextChoices):
    """Stable identifier for each event that sends an e-mail.

    Adding a notification takes three edits and no new machinery: a member
    here, an entry in ``apps.notifications.defaults.DEFAULTS`` for every
    configured language, and one ``send_notification`` call where the event
    happens. ``seed_notifications`` provisions the rows.
    """

    CONTACT_ENQUIRY_ADMIN = "contact_enquiry_admin", _("Contact enquiry - staff notification")
    CONTACT_ENQUIRY_USER = "contact_enquiry_user", _("Contact enquiry - sender confirmation")
{%- if cookiecutter.newsletter == "yes" %}
    NEWSLETTER_SUBSCRIBED = "newsletter_subscribed", _("Newsletter - confirm subscription")
{%- endif %}


class NotificationTemplate(models.Model):
    """Subject and body for one ``(trigger, language)`` pair."""

    trigger = models.CharField(
        max_length=64,
        choices=NotificationTrigger.choices,
        verbose_name=_("Trigger"),
    )
    language = models.CharField(
        max_length=16,
        choices=language_choices,
        verbose_name=_("Language"),
    )
    subject = models.CharField(max_length=255, verbose_name=_("Subject"))
    body = models.TextField(
        blank=True,
        verbose_name=_("Body"),
        help_text=_(
            "Plain-text Django template source. Placeholders are written as "
            "{% raw %}{{ name }}{% endraw %}; conditions as "
            "{% raw %}{% if phone %}...{% endif %}{% endraw %}."
        ),
    )
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("Last updated"))

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["trigger", "language"],
                name="notifications_unique_template_per_language",
            )
        ]
        ordering = ["trigger", "language"]
        verbose_name = _("E-mail template")
        verbose_name_plural = _("E-mail templates")

    def __str__(self):
        return f"{self.get_trigger_display()} ({self.language})"

    def default(self, field_name: str) -> str:
        """This row's built-in value for ``field_name``."""
        return get_default(self.trigger, self.language, field_name)

    def reset_field(self, field_name: str) -> None:
        """Restore one field to its built-in value.

        Only the named field is written, so resetting a subject cannot silently
        revert an edited body saved in the same session.
        """
        if field_name not in RESETTABLE_FIELDS:
            raise ValueError(f"{field_name} is not resettable")
        setattr(self, field_name, self.default(field_name))
        self.save(update_fields=[field_name, "updated_at"])

    def clean(self):
        # Imported here rather than at module scope: services imports this
        # module, and validation is only ever needed at save time.
        from apps.notifications.services import check_template_source

        errors = {}
        for field_name in RESETTABLE_FIELDS:
            error = check_template_source(getattr(self, field_name, ""))
            if error is not None:
                errors[field_name] = error
        if errors:
            raise ValidationError(errors)


class NotificationRecipient(models.Model):
    """The staff addresses one trigger notifies.

    A comma-separated list rather than a relation to user accounts: the people
    who must see an enquiry are often a shared inbox or someone without a login,
    and the client changes them without our help.
    """

    trigger = models.CharField(
        max_length=64,
        choices=NotificationTrigger.choices,
        unique=True,
        verbose_name=_("Trigger"),
    )
    recipients = models.TextField(
        blank=True,
        verbose_name=_("Recipients"),
        help_text=_("Comma-separated e-mail addresses that receive this notification."),
    )

    class Meta:
        ordering = ["trigger"]
        verbose_name = _("Notification recipient")
        verbose_name_plural = _("Notification recipients")

    def __str__(self):
        return str(self.get_trigger_display())

    def clean(self):
        for address in _split_addresses(self.recipients):
            try:
                validate_email(address)
            except ValidationError:
                raise ValidationError(
                    {
                        "recipients": _("%(address)s is not a valid e-mail address.")
                        % {"address": address}
                    }
                ) from None

    def as_list(self) -> list[str]:
        return _split_addresses(self.recipients)
