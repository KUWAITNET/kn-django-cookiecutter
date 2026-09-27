"""Make wagtail-2fa's sign-in and device set-up work reliably.

Three defects, all of which surfaced on a live KUWAITNET project as "Invalid code" or
"Invalid token" for a code the user could see was right.

**1. Sign-in under django-otp 1.7+.**

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
first version of this patch refused that case outright, which locked such
accounts out.

**2. Setting up a device.** wagtail-2fa's "add device" page deletes the pending
device and creates a new one - with a new secret - on *every* load, and serves
the QR code as a separate request. A refresh, a second tab, the back button or
a colleague opening the same page replaces the secret the user has just
scanned, and every code from their app is then "Invalid token". The pending
device is now reused until it is confirmed, so a scanned QR code stays valid.

**3. Codes typed with a space.** Authenticator apps display "123 456", and
people type or paste it that way. Whitespace is stripped before verification
on both forms.

Remove this module once wagtail-2fa fixes all three upstream.

Installed from ``CoreConfig.ready()``; applying it twice is harmless.
"""

import time

from django_otp.oath import TOTP
from django_otp.plugins.otp_totp.models import TOTPDevice
from wagtail_2fa import utils as wagtail_2fa_utils
from wagtail_2fa.forms import DeviceForm, TokenForm

_original_chosen_device = TokenForm._chosen_device
_original_new_unconfirmed_device = wagtail_2fa_utils.new_unconfirmed_device
_original_device_clean_otp_token = DeviceForm.clean_otp_token


def _normalise(token):
    return "".join(str(token or "").split())


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


def _token_clean_otp_token(self):
    """Sign-in form: strip the spaces authenticator apps display."""
    return _normalise(self.cleaned_data.get("otp_token"))


def _device_clean_otp_token(self):
    """Set-up form: strip spaces, then wagtail-2fa's own check."""
    self.cleaned_data["otp_token"] = _normalise(self.cleaned_data.get("otp_token"))
    return _original_device_clean_otp_token(self)


def _new_unconfirmed_device(user):
    """Reuse the pending device, so a reload never invalidates a scanned QR code."""
    pending = TOTPDevice.objects.devices_for_user(user, confirmed=False).first()
    return pending if pending is not None else _original_new_unconfirmed_device(user)


if not getattr(TokenForm._chosen_device, "_kuwaitnet_patched", False):
    _chosen_device._kuwaitnet_patched = True
    TokenForm._chosen_device = _chosen_device
    TokenForm.clean_otp_token = _token_clean_otp_token
    DeviceForm.clean_otp_token = _device_clean_otp_token
    wagtail_2fa_utils.new_unconfirmed_device = _new_unconfirmed_device
