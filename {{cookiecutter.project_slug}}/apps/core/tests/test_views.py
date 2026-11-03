"""Operational endpoints, robots.txt and the project 404.

Private files have their own module: test_private_files.py.
"""

import json

import pytest
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


def test_unknown_url_returns_the_project_404(client):
    # follow=True because a bilingual install redirects an unprefixed path to the
    # active language before it can 404.
    response = client.get("/this-page-does-not-exist/", follow=True)
    assert response.status_code == 404
