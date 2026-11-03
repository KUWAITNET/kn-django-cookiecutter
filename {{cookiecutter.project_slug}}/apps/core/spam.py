"""Bot protection for public forms.

Two layers, because they fail differently:

* a **honeypot** field - free, invisible to people, catches the naive scripted
  submitters that make up most form spam;
{%- if cookiecutter.spam_protection == "turnstile_honeypot" %}
* **Cloudflare Turnstile** - a real challenge for the rest.

Turnstile degrades to honeypot-only when no secret key is configured, so
development, CI and UAT are never blocked by a missing credential. Production
without a key is a go-live finding, and a deployment check says so.
{%- else %}
* Turnstile was not selected for this project, so the honeypot is the only layer.
  Record the exception in docs/decisions.md.
{%- endif %}

Every public form mixes in ``SpamProtectedForm``. The reference project had no bot
protection at all on seven unauthenticated POST endpoints, one of which sent an
e-mail per request.
"""

import logging

from django import forms
{%- if cookiecutter.spam_protection == "turnstile_honeypot" %}
from django.conf import settings
{%- endif %}
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

logger = logging.getLogger("{{ cookiecutter.project_slug }}")

#: Named after a field a form plausibly has, so a bot's field-name heuristics fill
#: it in. Renaming it per project is a small, free improvement.
HONEYPOT_FIELD_NAME = "website_url"

TURNSTILE_FIELD_NAME = "cf-turnstile-response"

#: One message for every rejection path. A bot that can tell "honeypot filled"
#: apart from "captcha failed" learns which control to work around; a person only
#: ever sees this after a genuine mistake.
SPAM_REJECTION_MESSAGE = _("Your submission could not be processed. Please try again.")


class HoneypotWidget(forms.TextInput):
    """Hidden from people without being ``type="hidden"``, which bots skip."""

    def __init__(self, attrs=None):
        defaults = {
            "autocomplete": "off",
            "tabindex": "-1",
            "aria-hidden": "true",
            "style": "position:absolute;left:-9999px;width:1px;height:1px;opacity:0;",
        }
        defaults.update(attrs or {})
        super().__init__(attrs=defaults)
{%- if cookiecutter.spam_protection == "turnstile_honeypot" %}


def turnstile_configured() -> bool:
    """Whether a secret key is available to verify against."""
    return bool(getattr(settings, "TURNSTILE_SECRET_KEY", ""))


def verify_turnstile(token: str, remote_ip: str = "") -> bool:
    """Ask Cloudflare whether ``token`` is valid.

    Fails closed. If Cloudflare cannot be reached the submission is rejected
    rather than waved through - an outage must not silently disable the control -
    and the failure is logged so the cause is visible.
    """
    import requests

    if not token:
        return False
    payload = {"secret": settings.TURNSTILE_SECRET_KEY, "response": token}
    if remote_ip:
        payload["remoteip"] = remote_ip
    try:
        response = requests.post(
            settings.TURNSTILE_VERIFY_URL,
            data=payload,
            timeout=settings.TURNSTILE_TIMEOUT,
        )
        response.raise_for_status()
        result = response.json()
    except requests.RequestException:
        # Covers timeouts, connection errors, a non-2xx status and a body that is
        # not JSON (requests raises a RequestException subclass for all of them).
        logger.warning("Turnstile verification could not be completed", exc_info=True)
        return False
    if not result.get("success"):
        logger.info("Turnstile rejected a submission: %s", result.get("error-codes"))
        return False
    return True
{%- endif %}


class SpamProtectedForm:
    """Mixin adding bot protection to any ``Form``/``ModelForm``.

    Place it first in the bases so its ``__init__``/``clean`` run::

        class ContactForm(SpamProtectedForm, forms.ModelForm):
            ...

    Views pass ``request=request`` so the client IP reaches Turnstile.
    """

    honeypot_field_name = HONEYPOT_FIELD_NAME

    def __init__(self, *args, request=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.request = request
        self.fields[self.honeypot_field_name] = forms.CharField(
            required=False,
            label="",
            widget=HoneypotWidget(),
            # Screen readers announce this; people who reach it must be able to
            # tell it is not for them.
            help_text=_("Leave this field empty."),
        )

    def clean(self):
        cleaned_data = super().clean()
        if self.cleaned_data.get(self.honeypot_field_name):
            # Identical to any other validation failure, and no field-level error
            # pointing at the honeypot: the bot must not learn what caught it.
            raise ValidationError(SPAM_REJECTION_MESSAGE, code="spam")
{%- if cookiecutter.spam_protection == "turnstile_honeypot" %}
        if turnstile_configured():
            from apps.core.utils import get_client_ip

            token = self.data.get(TURNSTILE_FIELD_NAME, "")
            remote_ip = get_client_ip(self.request) if self.request is not None else ""
            if not verify_turnstile(token, remote_ip=remote_ip):
                raise ValidationError(SPAM_REJECTION_MESSAGE, code="spam")
{%- endif %}
        return cleaned_data
