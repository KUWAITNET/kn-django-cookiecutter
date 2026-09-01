"""Pagination, filtering, ordering and search contract tests (api-standard.md A7)."""

import pytest
from django.urls import reverse

from apps.api.models import Note
from apps.api.pagination import DefaultPagination
from apps.api.views import NoteViewSet

pytestmark = pytest.mark.django_db


@pytest.fixture
def many_notes(owner):
    Note.objects.bulk_create(
        Note(owner=owner, title=f"Note {index:03d}", body="Body text") for index in range(105)
    )
    return Note.objects.filter(owner=owner)


def test_the_list_envelope_is_the_documented_shape(owner_client, note):
    response = owner_client.get(reverse("v1:note-list"))

    assert response.status_code == 200
    assert set(response.data) == {"count", "next", "previous", "results"}
    assert response.data["count"] == 1


def test_default_page_size_is_twenty(owner_client, many_notes):
    response = owner_client.get(reverse("v1:note-list"))

    assert len(response.data["results"]) == DefaultPagination.page_size == 20
    assert response.data["next"] is not None


def test_page_size_cannot_be_pushed_past_the_maximum(owner_client, many_notes):
    """A request for more than the cap is clamped server-side, not honoured."""
    response = owner_client.get(reverse("v1:note-list"), {"page_size": 100000})

    assert response.status_code == 200
    assert response.data["count"] == 105
    assert len(response.data["results"]) == DefaultPagination.max_page_size == 100


def test_ordering_on_the_allowlist_is_honoured(owner_client, many_notes):
    response = owner_client.get(reverse("v1:note-list"), {"ordering": "title"})

    assert response.status_code == 200
    titles = [row["title"] for row in response.data["results"]]
    assert titles == sorted(titles)


def test_ordering_outside_the_allowlist_is_rejected(owner_client, note):
    """Not silently ignored: a client that sorts by the wrong key must be told."""
    response = owner_client.get(reverse("v1:note-list"), {"ordering": "owner__password"})

    assert response.status_code == 400
    assert response["Content-Type"] == "application/problem+json"
    assert [error["field"] for error in response.data["errors"]] == ["ordering"]


def test_the_default_ordering_ends_in_a_unique_tiebreaker():
    """Without one, pagination loses and repeats rows when timestamps collide."""
    assert NoteViewSet.ordering[-1] in {"-id", "id", "-pk", "pk"}


def test_filtering_uses_the_declared_filterset(owner_client, owner):
    Note.objects.create(owner=owner, title="Draft note", body="x")
    published = Note.objects.create(
        owner=owner, title="Published note", body="x", status=Note.Status.PUBLISHED
    )

    response = owner_client.get(reverse("v1:note-list"), {"status": Note.Status.PUBLISHED})

    assert response.status_code == 200
    assert [row["uuid"] for row in response.data["results"]] == [str(published.uuid)]


def test_search_uses_the_declared_search_fields(owner_client, owner):
    match = Note.objects.create(owner=owner, title="Quarterly report", body="x")
    Note.objects.create(owner=owner, title="Shopping list", body="x")

    response = owner_client.get(reverse("v1:note-list"), {"search": "quarterly"})

    assert [row["uuid"] for row in response.data["results"]] == [str(match.uuid)]


def test_the_read_serializer_never_exposes_the_primary_key(owner_client, note):
    response = owner_client.get(reverse("v1:note-detail", kwargs={"uuid": str(note.uuid)}))

    assert response.status_code == 200
    assert "id" not in response.data
    assert "pk" not in response.data
    # The embedded owner is a summary, never the whole user record.
    assert set(response.data["owner"]) == {"username", "display_name"}


def test_timestamps_are_utc_with_a_z_suffix(owner_client, note):
    response = owner_client.get(reverse("v1:note-detail", kwargs={"uuid": str(note.uuid)}))

    assert response.data["created_at"].endswith("Z")
