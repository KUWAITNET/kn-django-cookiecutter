"""Operational endpoints, robots.txt and permission-checked private media."""

import json

import pytest
from django.contrib.auth.models import Permission
from django.urls import reverse

pytestmark = pytest.mark.django_db


def test_healthz_reports_ok_and_touches_the_database(client):
    response = client.get(reverse("healthz"))
    assert response.status_code == 200
    payload = json.loads(response.content)
    assert payload["status"] == "ok"
    # A probe that does not reach the database reports "healthy" while every page
    # is a 500, so the database key is the part that matters.
    assert payload["database"] == "ok"


def test_healthz_is_never_cached(client):
    response = client.get(reverse("healthz"))
    assert "no-cache" in response.headers.get("Cache-Control", "")
{%- if cookiecutter.frontend != "api_only" %}


def test_robots_disallows_everything_when_the_flag_is_set(client, settings):
    settings.DEBUG = False
    settings.ROBOTS_DISALLOW_ALL = True
    response = client.get("/robots.txt")
    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/plain")
    # Staging and UAT must never be indexed alongside the real site.
    assert "Disallow: /" in response.content.decode()


def test_robots_advertises_the_sitemap_when_indexing_is_allowed(client, settings):
    settings.DEBUG = False
    settings.ROBOTS_DISALLOW_ALL = False
    response = client.get("/robots.txt")
    assert response.status_code == 200
    assert "sitemap.xml" in response.content.decode().lower()
{%- endif %}


# --- Private media -----------------------------------------------------------


@pytest.fixture
def private_file():
    """A real file in the private store, plus the name the view is given.

    Written through the configured private storage rather than straight to disk,
    so the fixture stays correct whichever backend the project selected - the
    view reads it back through the same storage.
    """
    from django.core.files.base import ContentFile

    from apps.core.storage import private_media_storage

    storage = private_media_storage()
    name = storage.save("submissions/cv.pdf", ContentFile(b"%PDF-1.4 confidential"))
    yield name
    storage.delete(name)


def _grant_private_media(user):
    user.user_permissions.add(Permission.objects.get(codename="access_private_media"))
    return user


def test_anonymous_access_is_denied(client, private_file):
    response = client.get(reverse("private_media", args=[private_file]))
    assert response.status_code == 403


def test_staff_without_the_permission_is_denied(client, staff_user, private_file):
    client.force_login(staff_user)
    # is_staff is not authorisation: the permission is what grants access.
    response = client.get(reverse("private_media", args=[private_file]))
    assert response.status_code == 403


def test_permitted_user_gets_the_file_as_an_attachment(client, staff_user, private_file):
    client.force_login(_grant_private_media(staff_user))
    response = client.get(reverse("private_media", args=[private_file]))
    assert response.status_code == 200
    assert response["Content-Disposition"].startswith("attachment")
    assert response["X-Content-Type-Options"] == "nosniff"
    assert b"confidential" in b"".join(response.streaming_content)


@pytest.mark.parametrize(
    "traversal",
    [
        "../../../etc/passwd",
        "submissions/../../../etc/passwd",
        "/etc/passwd",
    ],
)
def test_path_traversal_is_rejected(client, staff_user, private_file, traversal):
    client.force_login(_grant_private_media(staff_user))
    response = client.get(f"/private-media/{traversal}")
    assert response.status_code in (404, 403)


def test_missing_file_is_a_404_not_a_500(client, staff_user, private_file):
    client.force_login(_grant_private_media(staff_user))
    response = client.get(reverse("private_media", args=["submissions/nope.pdf"]))
    assert response.status_code == 404


def test_unknown_url_returns_the_project_404(client):
    # follow=True because a bilingual install redirects an unprefixed path to the
    # active language before it can 404.
    response = client.get("/this-page-does-not-exist/", follow=True)
    assert response.status_code == 404
