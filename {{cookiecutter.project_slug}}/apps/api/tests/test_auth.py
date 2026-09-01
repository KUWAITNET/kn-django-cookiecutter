"""JWT authentication contract tests (api-standard.md A4)."""

import pytest
from django.urls import reverse

from apps.api.tests.conftest import OWNER_PASSWORD
from apps.api.throttling import AuthRateThrottle

pytestmark = pytest.mark.django_db


def obtain(api_client, username=None, password=OWNER_PASSWORD):
    return api_client.post(
        reverse("v1:token-obtain"),
        {"username": username or "owner", "password": password},
    )


def test_obtain_returns_an_access_and_refresh_pair(api_client, owner):
    response = obtain(api_client)

    assert response.status_code == 200
    assert set(response.data) == {"access", "refresh"}


def test_bad_credentials_are_401_problem_json(api_client, owner):
    response = obtain(api_client, password="wrong-password")

    assert response.status_code == 401
    assert response["Content-Type"] == "application/problem+json"
    assert response.data["status"] == 401


def test_an_access_token_authenticates_a_request(api_client, owner, note):
    access = obtain(api_client).data["access"]

    response = api_client.get(reverse("v1:note-list"), HTTP_AUTHORIZATION=f"Bearer {access}")

    assert response.status_code == 200
    assert response.data["count"] == 1


def test_refresh_rotates_the_token_and_blacklists_the_old_one(api_client, owner):
    original_refresh = obtain(api_client).data["refresh"]
    url = reverse("v1:token-refresh")

    rotated = api_client.post(url, {"refresh": original_refresh})
    assert rotated.status_code == 200
    assert rotated.data["refresh"] != original_refresh

    # A refresh token presented twice must fail. That is also the detection
    # signal for a stolen token, and is worth alerting on in production.
    replayed = api_client.post(url, {"refresh": original_refresh})
    assert replayed.status_code == 401
    assert replayed["Content-Type"] == "application/problem+json"


def test_verify_accepts_a_live_token_and_rejects_a_forged_one(api_client, owner):
    access = obtain(api_client).data["access"]
    url = reverse("v1:token-verify")

    assert api_client.post(url, {"token": access}).status_code == 200
    assert api_client.post(url, {"token": "not-a-token"}).status_code == 401


def test_logout_blacklists_the_refresh_token(api_client, owner):
    refresh = obtain(api_client).data["refresh"]

    assert api_client.post(reverse("v1:token-blacklist"), {"refresh": refresh}).status_code == 200
    assert api_client.post(reverse("v1:token-refresh"), {"refresh": refresh}).status_code == 401


def test_token_obtain_carries_the_auth_throttle_scope(api_client, owner, monkeypatch):
    """A login endpoint is a credential oracle, so it is the tightest scope."""
    monkeypatch.setattr(AuthRateThrottle, "rate", "1/min", raising=False)

    assert obtain(api_client).status_code == 200
    throttled = obtain(api_client)

    assert throttled.status_code == 429
    assert throttled["Retry-After"]
