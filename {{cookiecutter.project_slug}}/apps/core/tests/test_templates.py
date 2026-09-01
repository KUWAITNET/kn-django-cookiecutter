"""Smoke tests for the server-rendered shell.

Status codes plus the handful of context values every template depends on: if the
context processor stops supplying one, the page still renders but silently loses
its title, its canonical link or its language switcher.
"""

import pytest

pytestmark = pytest.mark.django_db

REQUIRED_CONTEXT_KEYS = [
    "SITE_NAME",
    "CLIENT_NAME",
    "BASE_URL",
    "SPAM_PROTECTION",
    "LANGUAGES_AVAILABLE",
]


def test_the_home_page_renders(client):
    response = client.get("/", follow=True)
    assert response.status_code == 200


def test_the_shared_context_is_available_to_every_template(client):
    response = client.get("/", follow=True)
    for key in REQUIRED_CONTEXT_KEYS:
        assert key in response.context, f"{key} missing from the template context"
    assert response.context["SITE_NAME"]


def test_every_language_alternative_has_a_usable_url(client):
    response = client.get("/", follow=True)
    alternatives = response.context["LANGUAGES_AVAILABLE"]
    assert alternatives
    for entry in alternatives:
        # An empty URL is allowed (no version in that language) but a relative
        # one is not: hreflang and og:url must be absolute.
        assert entry["url"] == "" or entry["url"].startswith("http")


def test_error_pages_render_rather_than_raising(client):
    response = client.get("/definitely-not-a-page/", follow=True)
    assert response.status_code == 404
