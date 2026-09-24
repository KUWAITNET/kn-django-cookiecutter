"""Let wagtail-2fa's sign-in form verify a code under django-otp 1.7+.

django-otp 1.7 stopped trying every one of a user's devices when a form does
not say which device a code belongs to: ``OTPAuthenticationFormMixin`` now
raises unless ``otp_device`` names one, because trying each device records a
failed attempt against every device that did not match and can throttle one the
user never touched. wagtail-2fa 1.8 (the current release) still posts only
``otp_token``. Without this patch every code is refused at sign-in with
"Invalid code" - while enrolment, which goes through a different form, keeps
working, which is what makes the fault look like the user's mistake.

The patch keeps django-otp's rule - one explicit device per attempt - and makes
the choice the form cannot: the user's confirmed device when they have exactly
one, which is the only case wagtail-2fa's own screens create. A user with
several devices is still refused rather than having every device tried.

Remove this module once wagtail-2fa sends ``otp_device`` itself.

Installed from ``CoreConfig.ready()``; applying it twice is harmless.
"""

from django_otp import devices_for_user
from wagtail_2fa.forms import TokenForm

_original_chosen_device = TokenForm._chosen_device


def _chosen_device(self, user):
    device = _original_chosen_device(self, user)
    if device is not None:
        return device
    confirmed = list(devices_for_user(user, confirmed=True))
    return confirmed[0] if len(confirmed) == 1 else None


if not getattr(TokenForm._chosen_device, "_kuwaitnet_patched", False):
    _chosen_device._kuwaitnet_patched = True
    TokenForm._chosen_device = _chosen_device
