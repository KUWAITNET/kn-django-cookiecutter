"""Object-level authorisation contract tests (api-standard.md A5, OWASP API1).

Both halves of the rule are asserted independently: that the queryset is scoped,
and that an object permission exists. A reviewer who sees one and assumes the
other is the mechanism by which this bug ships, so the tests do not assume it
either.
"""

import uuid

import pytest
from django.urls import reverse
from rest_framework.test import APIRequestFactory

from apps.api.models import Note
from apps.api.permissions import IsObjectOwner

pytestmark = pytest.mark.django_db


def detail_url(note):
    return reverse("v1:note-detail", kwargs={"uuid": str(note.uuid)})


def publish_url(note):
    return reverse("v1:note-publish", kwargs={"uuid": str(note.uuid)})


# -- unauthenticated ------------------------------------------------------


def test_anonymous_list_is_rejected(api_client):
    response = api_client.get(reverse("v1:note-list"))

    assert response.status_code == 401
    # JWT is listed first in DEFAULT_AUTHENTICATION_CLASSES precisely so that a
    # request with no credentials gets a 401 with a challenge, which is what
    # tells a client to refresh, rather than DRF's session-only 403.
    assert response["WWW-Authenticate"].startswith("Bearer")


def test_anonymous_create_is_rejected(api_client):
    response = api_client.post(reverse("v1:note-list"), {"title": "Sneaky", "body": "x"})

    assert response.status_code == 401
    assert Note.objects.count() == 0


def test_anonymous_detail_is_rejected(api_client, note):
    assert api_client.get(detail_url(note)).status_code == 401


# -- half one: the queryset is owner-filtered ------------------------------


def test_list_contains_only_the_callers_notes(owner_client, note, foreign_note):
    response = owner_client.get(reverse("v1:note-list"))

    assert response.status_code == 200
    returned = {row["uuid"] for row in response.data["results"]}
    assert returned == {str(note.uuid)}


def test_another_users_note_is_not_readable(owner_client, foreign_note):
    response = owner_client.get(detail_url(foreign_note))

    # 404, not 403: the queryset is owner-filtered, so we do not confirm that the
    # row exists at all.
    assert response.status_code == 404


def test_another_users_note_cannot_be_updated(owner_client, foreign_note):
    response = owner_client.patch(detail_url(foreign_note), {"title": "Hijacked"})

    assert response.status_code == 404
    foreign_note.refresh_from_db()
    assert foreign_note.title == "Another user note"


def test_another_users_note_cannot_be_deleted(owner_client, foreign_note):
    response = owner_client.delete(detail_url(foreign_note))

    assert response.status_code == 404
    assert Note.objects.filter(pk=foreign_note.pk).exists()


def test_another_users_note_cannot_be_published(owner_client, foreign_note):
    """The custom action resolves through get_object(), so it inherits the scope."""
    response = owner_client.post(publish_url(foreign_note))

    assert response.status_code == 404
    foreign_note.refresh_from_db()
    assert foreign_note.status == Note.Status.DRAFT


def test_a_note_that_does_not_exist_is_a_404(owner_client):
    url = reverse("v1:note-detail", kwargs={"uuid": str(uuid.uuid4())})

    assert owner_client.get(url).status_code == 404


# -- half two: the object permission exists and denies -----------------------


def test_object_permission_denies_a_foreign_object(owner, note, foreign_note):
    """Asserted directly, because a filtered queryset would hide its absence.

    If this class were deleted, every test above would still pass and the first
    custom action that fetched a row by id would have nothing stopping it.
    """
    request = APIRequestFactory().get("/")
    request.user = owner
    permission = IsObjectOwner()

    assert permission.has_object_permission(request, None, note) is True
    assert permission.has_object_permission(request, None, foreign_note) is False


# -- mass assignment (OWASP API3) --------------------------------------------


def test_client_supplied_owner_and_status_are_not_trusted(owner_client, owner, intruder):
    """Asserted from the attacker's side: the persisted row must not have changed."""
    response = owner_client.post(
        reverse("v1:note-list"),
        {
            "title": "Mine now",
            "body": "Body text",
            "owner": intruder.pk,
            "status": Note.Status.PUBLISHED,
        },
    )

    assert response.status_code == 201
    created = Note.objects.get(uuid=response.data["uuid"])
    assert created.owner_id == owner.pk
    assert created.status == Note.Status.DRAFT


def test_patch_cannot_move_a_note_to_another_owner(owner_client, note, owner, intruder):
    response = owner_client.patch(detail_url(note), {"owner": intruder.pk})

    assert response.status_code == 200
    note.refresh_from_db()
    assert note.owner_id == owner.pk


def test_publish_is_the_only_way_the_status_moves(owner_client, note):
    response = owner_client.post(publish_url(note))

    assert response.status_code == 200
    note.refresh_from_db()
    assert note.status == Note.Status.PUBLISHED


# -- the staff-gated diagnostic ----------------------------------------------


def test_diagnostic_rejects_anonymous_requests(api_client):
    """The reference project protected this with an unguessable URL. It is a login now."""
    response = api_client.get(reverse("v1:integration-diagnostic"))

    assert response.status_code == 401


def test_diagnostic_rejects_a_non_staff_user(owner_client):
    response = owner_client.get(reverse("v1:integration-diagnostic"))

    assert response.status_code == 403


def test_diagnostic_reports_an_unconfigured_integration_to_staff(api_client, staff_member):
    api_client.force_authenticate(user=staff_member)

    response = api_client.get(reverse("v1:integration-diagnostic"))

    assert response.status_code == 503
    assert response.data["status"] == "not_configured"
    # Never the upstream's own error text.
    assert response.data["error_class"] is None
