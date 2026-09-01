"""The RFC 9457 error envelope (api-standard.md A9).

The error contract is part of the API and is tested like the rest of it: one
content type and one set of members for every status code, and no DRF default
error shape anywhere.
"""

import uuid

import pytest
from django.urls import reverse
from rest_framework import exceptions
from rest_framework.test import APIRequestFactory

from apps.api.exceptions import (
    GENERIC_5XX_DETAIL,
    PROBLEM_CONTENT_TYPE,
    problem_detail_handler,
    problem_json_response,
)
from apps.api.models import Note
from apps.api.throttling import WriteRateThrottle

REQUIRED_MEMBERS = {"type", "title", "status", "detail", "instance", "request_id"}

pytestmark = pytest.mark.django_db


def assert_problem(response, expected_status):
    assert response.status_code == expected_status
    assert response["Content-Type"] == PROBLEM_CONTENT_TYPE
    body = response.data
    assert REQUIRED_MEMBERS <= set(body)
    assert body["status"] == expected_status
    assert body["type"].startswith("http")
    assert body["title"]
    assert body["instance"]
    assert body["request_id"]
    return body


def test_validation_failure_is_problem_json_with_field_errors(owner_client):
    response = owner_client.post(reverse("v1:note-list"), {"title": "no", "body": ""})

    body = assert_problem(response, 400)
    assert body["errors"]
    reported = {error["field"] for error in body["errors"]}
    assert "title" in reported
    for error in body["errors"]:
        assert set(error) == {"field", "code", "detail"}


def test_cross_field_validation_error_names_the_field(owner_client):
    response = owner_client.post(
        reverse("v1:note-list"), {"title": "Pinned note", "body": "", "is_pinned": True}
    )

    body = assert_problem(response, 400)
    assert [error["field"] for error in body["errors"]] == ["body"]


def test_unauthenticated_is_401_problem_json(api_client):
    response = api_client.get(reverse("v1:note-list"))

    assert_problem(response, 401)
    assert response["WWW-Authenticate"].startswith("Bearer")


def test_permission_denied_is_403_problem_json(owner_client):
    response = owner_client.get(reverse("v1:integration-diagnostic"))

    body = assert_problem(response, 403)
    # Identical wording for "not yours" and "not your role": distinguishing them
    # tells an attacker which object ids exist.
    assert "permission" in body["detail"].lower()


def test_not_found_is_404_problem_json(owner_client):
    url = reverse("v1:note-detail", kwargs={"uuid": str(uuid.uuid4())})

    assert_problem(owner_client.get(url), 404)


def test_method_not_allowed_is_405_problem_json(owner_client, note):
    response = owner_client.put(reverse("v1:note-list"), {"title": "Nope"})

    assert_problem(response, 405)


def test_throttled_request_is_429_with_retry_after(owner_client, monkeypatch):
    # DRF caches DEFAULT_THROTTLE_RATES on the class at import time, so
    # override_settings would not reach it; setting the rate directly does.
    monkeypatch.setattr(WriteRateThrottle, "rate", "1/min", raising=False)
    url = reverse("v1:note-list")

    assert owner_client.post(url, {"title": "First note", "body": "x"}).status_code == 201
    response = owner_client.post(url, {"title": "Second note", "body": "x"})

    body = assert_problem(response, 429)
    assert body["retry_after"] >= 1
    assert int(response["Retry-After"]) == body["retry_after"]
    assert Note.objects.count() == 1


def test_unhandled_exception_becomes_a_500_that_says_nothing():
    """A 5xx body never varies with the exception - request_id is the whole channel."""
    request = APIRequestFactory().get("/api/v1/notes/")
    try:
        raise RuntimeError("SELECT password FROM auth_user -- internal detail")
    except RuntimeError as exc:
        response = problem_detail_handler(exc, {"request": request})

    assert response.status_code == 500
    assert response.data["detail"] == GENERIC_5XX_DETAIL
    assert "SELECT" not in str(response.data)
    assert "RuntimeError" not in str(response.data)


def test_problem_json_response_helper_matches_the_envelope(rf):
    """Exported so Django-level handler404/handler500 can answer /api/ the same way."""
    request = rf.get("/api/v1/notes/does-not-exist/")

    response = problem_json_response(request, 404)

    assert response.status_code == 404
    assert response["Content-Type"] == PROBLEM_CONTENT_TYPE


def test_a_dict_detail_from_a_library_is_not_republished():
    """simplejwt raises detail dicts carrying its own ``messages`` list."""
    request = APIRequestFactory().get("/api/v1/notes/")
    exc = exceptions.AuthenticationFailed(
        {"detail": "Token is invalid", "messages": [{"token_class": "AccessToken"}]}
    )

    response = problem_detail_handler(exc, {"request": request})

    assert response.data["detail"] == "Token is invalid"
    assert "token_class" not in str(response.data)
