"""Shared fixtures for the API contract tests."""

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework.test import APIClient

from apps.api.models import Note

OWNER_PASSWORD = "owner-password-12345"
INTRUDER_PASSWORD = "intruder-password-12345"
STAFF_PASSWORD = "staff-password-12345"


@pytest.fixture(autouse=True)
def _reset_throttle_counters():
    """Throttle counters live in the cache and would otherwise leak between tests."""
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def owner(db):
    return get_user_model().objects.create_user(
        username="owner", email="owner@example.com", password=OWNER_PASSWORD
    )


@pytest.fixture
def intruder(db):
    return get_user_model().objects.create_user(
        username="intruder", email="intruder@example.com", password=INTRUDER_PASSWORD
    )


@pytest.fixture
def staff_member(db):
    return get_user_model().objects.create_user(
        username="staffer",
        email="staffer@example.com",
        password=STAFF_PASSWORD,
        is_staff=True,
    )


@pytest.fixture
def owner_client(api_client, owner):
    api_client.force_authenticate(user=owner)
    return api_client


@pytest.fixture
def note(owner):
    return Note.objects.create(owner=owner, title="Owner note", body="Body text")


@pytest.fixture
def foreign_note(intruder):
    return Note.objects.create(owner=intruder, title="Another user note", body="Body text")
