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


def test_a_user_with_several_devices_signs_in_with_either(client, admin_user, device):
    """Regression: a second device locked the account out ("Invalid code")."""
    second = TOTPDevice.objects.create(user=admin_user, name="tablet", confirmed=True)

    client.force_login(admin_user)
    response = client.post(VERIFY_URL, {"otp_token": _code(second)})

    assert response.status_code == 302
    assert client.session[DEVICE_ID_SESSION_KEY] == second.persistent_id


def test_a_matching_code_never_throttles_the_other_devices(client, admin_user, device):
    """django-otp's rule stands: only the device that matched is touched."""
    second = TOTPDevice.objects.create(user=admin_user, name="tablet", confirmed=True)

    client.force_login(admin_user)
    client.post(VERIFY_URL, {"otp_token": _code(second)})

    device.refresh_from_db()
    assert device.throttling_failure_count == 0


def test_a_wrong_code_is_still_counted_against_one_device(client, admin_user, device):
    TOTPDevice.objects.create(user=admin_user, name="tablet", confirmed=True)
    client.force_login(admin_user)

    client.post(VERIFY_URL, {"otp_token": "not-a-code"})

    failures = [d.throttling_failure_count for d in TOTPDevice.objects.filter(user=admin_user)]
    assert sorted(failures) == [0, 1]


def test_a_code_typed_with_a_space_signs_in(client, admin_user, device):
    code = _code(device)
    client.force_login(admin_user)

    response = client.post(VERIFY_URL, {"otp_token": f"{code[:3]} {code[3:]}"})

    assert response.status_code == 302


# --- Setting up a device -------------------------------------------------------

NEW_DEVICE_URL = f"/{settings.WAGTAIL_ADMIN_URL_PREFIX}/2fa/devices/new"


def _pending(user):
    return TOTPDevice.objects.get(user=user, confirmed=False)


def test_reloading_the_set_up_page_keeps_the_scanned_secret(client, admin_user):
    """Regression: every load replaced the secret, so a scanned QR code went stale."""
    client.force_login(admin_user)

    client.get(NEW_DEVICE_URL)
    scanned = _pending(admin_user).key
    client.get(NEW_DEVICE_URL)

    assert _pending(admin_user).key == scanned


def test_a_device_set_up_after_a_reload_is_confirmed(client, admin_user):
    client.force_login(admin_user)
    client.get(NEW_DEVICE_URL)
    scanned = _pending(admin_user)
    client.get(NEW_DEVICE_URL)

    code = _code(scanned)
    response = client.post(
        NEW_DEVICE_URL,
        {
            "name": "phone",
            "otp_token": f"{code[:3]} {code[3:]}",
            "password": "admin-password-for-tests",
        },
    )

    assert response.status_code == 302
    assert TOTPDevice.objects.get(pk=scanned.pk).confirmed is True


def test_a_wrong_set_up_code_is_still_refused(client, admin_user):
    client.force_login(admin_user)
    client.get(NEW_DEVICE_URL)

    response = client.post(
        NEW_DEVICE_URL,
        {"name": "phone", "otp_token": "not-a-code", "password": "admin-password-for-tests"},
    )

    assert response.status_code == 200
    assert not TOTPDevice.objects.filter(user=admin_user, confirmed=True).exists()
