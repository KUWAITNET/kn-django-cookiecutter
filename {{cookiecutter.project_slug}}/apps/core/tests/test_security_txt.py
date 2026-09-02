"""`/.well-known/security.txt` - RFC 9116.

The file exists so a vulnerability report reaches us by a route we chose. The
tests that matter are about it staying *valid*: an expired `Expires` field may be
ignored outright by a parser, at which point the site publishes a contact that
nobody's tooling will read, which is worse than publishing none because it looks
handled.
"""

from __future__ import annotations

from datetime import datetime, timezone as dt_timezone

import pytest
from django.conf import settings

# The view itself reads no model, but the middleware and context processors that
# run around it do, and which ones are active depends on the selected options.
# Marking the module is honest about that; marking each test is the same thing
# spelled four times.
pytestmark = pytest.mark.django_db


@pytest.fixture
def security_txt(client):
    response = client.get("/.well-known/security.txt")
    assert response.status_code == 200, "security.txt is not being served"
    return response


class TestServed:
    def test_is_plain_text(self, security_txt):
        assert security_txt["Content-Type"].startswith("text/plain")

    def test_at_the_exact_rfc_path(self, client):
        """RFC 9116 names one location. A near miss is not discoverable."""
        assert client.get("/.well-known/security.txt").status_code == 200

    def test_is_not_language_prefixed(self, client):
        """Scanners request the bare path, never `/en/.well-known/...`."""
        response = client.get("/.well-known/security.txt")
        assert response.status_code == 200


class TestContent:
    def test_declares_a_contact(self, security_txt):
        body = security_txt.content.decode()
        assert "Contact:" in body
        assert settings.SECURITY_CONTACT_EMAIL in body

    def test_expires_is_present_and_in_the_future(self, security_txt):
        """Mandatory in the RFC, and the whole point of generating it."""
        line = next(
            ln for ln in security_txt.content.decode().splitlines() if ln.startswith("Expires:")
        )
        value = line.split(":", 1)[1].strip()
        expires = datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.000Z").replace(
            tzinfo=dt_timezone.utc
        )
        assert expires > datetime.now(dt_timezone.utc), (
            "security.txt has expired; parsers are entitled to ignore the whole file"
        )

    def test_does_not_leak_the_admin_path(self, security_txt):
        """This file is world-readable and read mostly by people probing us."""
        body = security_txt.content.decode()
        assert settings.ADMIN_URL_PREFIX not in body
