"""Outbound integration contract tests (api-standard.md B2-B8).

The transport is mocked throughout: CI never calls a real vendor.
"""

import ssl
from unittest import mock

import pytest
import requests
from django.test import override_settings

from apps.api.services import (
    ExampleIntegrationClient,
    MinimumTLS12Adapter,
    PinnedTLS12Adapter,
    UpstreamMisconfigured,
    UpstreamRejected,
    UpstreamUnavailable,
)

CONFIGURED = {
    "INTEGRATION_BASE_URL": "https://upstream.example.com/api",
    "INTEGRATION_USERNAME": "service-account",
    "INTEGRATION_PASSWORD": "not-a-real-password",
}


@pytest.fixture
def client(settings):
    for name, value in CONFIGURED.items():
        setattr(settings, name, value)
    return ExampleIntegrationClient()


class FakeResponse:
    """The smallest surface the client actually uses."""

    def __init__(self, status_code, payload=None, malformed=False):
        self.status_code = status_code
        self._payload = payload
        self._malformed = malformed

    def json(self):
        if self._malformed:
            raise ValueError("the body is not JSON")
        return self._payload


def fake_response(status_code, payload=None, malformed=False):
    return FakeResponse(status_code, payload, malformed)


# -- the settings guard ---------------------------------------------------


def test_an_unconfigured_integration_is_absent_not_broken():
    """The app boots without the credential; only using it complains."""
    assert ExampleIntegrationClient.is_configured() is False


def test_missing_settings_raise_a_clear_error_before_any_network_call():
    with pytest.raises(UpstreamMisconfigured) as excinfo:
        ExampleIntegrationClient()

    message = str(excinfo.value)
    for name in ExampleIntegrationClient._REQUIRED_SETTINGS:
        assert name in message


@override_settings(**CONFIGURED)
def test_is_configured_is_true_once_every_setting_is_present():
    assert ExampleIntegrationClient.is_configured() is True


# -- timeouts, retries and TLS --------------------------------------------


def test_both_timeouts_are_explicit(client):
    connect, read = client._timeout

    assert connect > 0
    assert read > 0


def test_every_call_passes_the_timeout(client):
    with mock.patch.object(client._session, "request") as request:
        request.return_value = fake_response(200, {"ok": True})
        client.ping()

    assert request.call_args.kwargs["timeout"] == client._timeout


def test_post_is_not_retried(client):
    """A read timeout on a non-idempotent call can double-charge if replayed."""
    retry = client._session.get_adapter("https://upstream.example.com/").max_retries

    assert "POST" not in retry.allowed_methods
    assert "GET" in retry.allowed_methods
    assert retry.total == 2
    assert retry.read == 0
    assert retry.respect_retry_after_header is True


def test_tls_verification_is_never_disabled_and_the_floor_is_tls12():
    """Asserted on the adapter's own context, so a refactor cannot remove it quietly."""
    context = MinimumTLS12Adapter().poolmanager.connection_pool_kw["ssl_context"]

    assert context.minimum_version is ssl.TLSVersion.TLSv1_2
    assert context.verify_mode is ssl.CERT_REQUIRED


def test_pinning_tls12_is_opt_in_and_explicit():
    assert MinimumTLS12Adapter.maximum_tls_version is None
    assert PinnedTLS12Adapter.maximum_tls_version is ssl.TLSVersion.TLSv1_2


# -- failure handling ------------------------------------------------------


@pytest.mark.parametrize(
    ("side_effect", "expected"),
    [
        (requests.Timeout("read timed out"), UpstreamUnavailable),
        (requests.ConnectionError("connection refused"), UpstreamUnavailable),
        (requests.TooManyRedirects("too many redirects"), UpstreamUnavailable),
    ],
)
def test_transport_failures_become_our_exception(client, side_effect, expected):
    with mock.patch.object(client._session, "request", side_effect=side_effect):
        with pytest.raises(expected):
            client.ping()


def test_a_5xx_is_unavailable_and_a_4xx_is_rejected(client):
    with mock.patch.object(client._session, "request") as request:
        request.return_value = fake_response(503)
        with pytest.raises(UpstreamUnavailable):
            client.ping()

        request.return_value = fake_response(401)
        with pytest.raises(UpstreamRejected):
            client.ping()


def test_a_malformed_body_is_unavailable_not_a_crash(client):
    with mock.patch.object(client._session, "request") as request:
        request.return_value = fake_response(200, malformed=True)
        with pytest.raises(UpstreamUnavailable):
            client.ping()


def test_our_messages_never_carry_the_upstreams_own_text(client):
    upstream_text = "WS-Security fault at https://internal.vendor.local/svc user=svc_admin"
    with mock.patch.object(client._session, "request") as request:
        request.return_value = fake_response(500, {"error": upstream_text})
        with pytest.raises(UpstreamUnavailable) as excinfo:
            client.ping()

    assert upstream_text not in str(excinfo.value)
    assert "internal.vendor.local" not in str(excinfo.value)


def test_the_service_layer_returns_plain_data(client):
    with mock.patch.object(client._session, "request") as request:
        request.return_value = fake_response(200, {"reference": "ABC-1", "amount": "12.50"})
        result = client.fetch_record("ABC-1")

    assert result == {"reference": "ABC-1", "amount": "12.50"}
    assert isinstance(result, dict)
