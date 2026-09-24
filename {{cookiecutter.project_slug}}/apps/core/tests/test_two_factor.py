"""Two-factor sign-in accepts a valid code.

Regression test: under django-otp 1.7 with wagtail-2fa 1.8 every code was
refused at sign-in ("Invalid code") while enrolment kept working. The test
settings switch the 2FA requirement off for the rest of the suite, so this goes
through the real verify view on purpose.
"""

import time

import pytest
from django.conf import settings
from django_otp import DEVICE_ID_SESSION_KEY
from django_otp.oath import TOTP
from django_otp.plugins.otp_totp.models import TOTPDevice

pytestmark = pytest.mark.django_db

VERIFY_URL = f"/{settings.WAGTAIL_ADMIN_URL_PREFIX}/2fa/auth"


def _code(device, offset=0):
    totp = TOTP(device.bin_key, device.step, device.t0, device.digits, device.drift)
    totp.time = time.time() + offset
    return f"{totp.token():0{device.digits}d}"


@pytest.fixture
def device(admin_user):
    return TOTPDevice.objects.create(user=admin_user, name="phone", confirmed=True)


def test_a_valid_code_signs_the_user_in(client, admin_user, device):
    client.force_login(admin_user)

    response = client.post(VERIFY_URL, {"otp_token": _code(device)})

    assert response.status_code == 302
    assert client.session[DEVICE_ID_SESSION_KEY] == device.persistent_id


def test_a_wrong_code_is_refused(client, admin_user, device):
    client.force_login(admin_user)

    response = client.post(
        VERIFY_URL, {"otp_token": "000000" if _code(device) != "000000" else "111111"}
    )

    assert response.status_code == 200
    assert DEVICE_ID_SESSION_KEY not in client.session


def test_a_code_cannot_be_replayed(client, admin_user, device):
    code = _code(device)
    client.force_login(admin_user)
    client.post(VERIFY_URL, {"otp_token": code})
    client.logout()
    client.force_login(admin_user)

    response = client.post(VERIFY_URL, {"otp_token": code})

    assert response.status_code == 200


def test_a_user_with_several_devices_is_not_guessed_for(client, admin_user, device):
    """django-otp's rule stands: the patch never tries every device in turn."""
    TOTPDevice.objects.create(user=admin_user, name="tablet", confirmed=True)
    client.force_login(admin_user)

    response = client.post(VERIFY_URL, {"otp_token": _code(device)})

    assert response.status_code == 200
