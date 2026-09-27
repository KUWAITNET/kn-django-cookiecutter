"""Let wagtail-2fa's sign-in form verify a code under django-otp 1.7+.

django-otp 1.7 stopped trying every one of a user's devices when a form does
not say which device a code belongs to: ``OTPAuthenticationFormMixin`` now
raises unless ``otp_device`` names one, because trying each device records a
failed attempt against every device that did not match and can throttle one the
user never touched. wagtail-2fa 1.8 (the current release) still posts only
``otp_token``. Without this patch every code is refused at sign-in with
"Invalid code" - while enrolment, which goes through a different form, keeps
working, which is what makes the fault look like the user's mistake.

The patch keeps django-otp's rule - exactly one device is verified per attempt -
and makes the choice the form cannot:

* the code is matched against each confirmed TOTP device with a pure
  calculation (``TOTP.verify``), which saves nothing and throttles nothing;
* the device it matches is the one handed to the form, which then verifies it
  for real and records the success;
* when nothing matches, the most recently used device is handed over, so the
  failed attempt is still counted - against one device, not all of them.

A user with several devices is normal: wagtail-2fa lets anyone add a second one
from the device list, and an enrolment that is started twice leaves two. The
first version of this patch refused that case outright, which locked the dev
site admin account of a generated project out.

Remove this module once wagtail-2fa sends ``otp_device`` itself.

Installed from ``CoreConfig.ready()``; applying it twice is harmless.
"""

import time

from django_otp.oath import TOTP
from django_otp.plugins.otp_totp.models import TOTPDevice
from wagtail_2fa.forms import TokenForm

_original_chosen_device = TokenForm._chosen_device


def _matches(device, token):
    """Whether ``token`` is a current, unused code for ``device``. No side effects."""
    try:
        token = int(token)
    except TypeError, ValueError:
        return False
    totp = TOTP(device.bin_key, device.step, device.t0, device.digits, device.drift)
    totp.time = time.time()
    return totp.verify(token, device.tolerance, device.last_t + 1)


def _chosen_device(self, user):
    device = _original_chosen_device(self, user)
    if device is not None:
        return device
    devices = list(
        TOTPDevice.objects.filter(user=user, confirmed=True).order_by("-last_used_at", "-id")
    )
    if not devices:
        return None
    token = self.cleaned_data.get("otp_token")
    return next((d for d in devices if _matches(d, token)), devices[0])


if not getattr(TokenForm._chosen_device, "_kuwaitnet_patched", False):
    _chosen_device._kuwaitnet_patched = True
    TokenForm._chosen_device = _chosen_device
