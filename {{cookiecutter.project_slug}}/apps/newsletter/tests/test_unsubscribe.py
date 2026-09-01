import uuid

import pytest
from django.test import Client
from django.urls import reverse

from apps.newsletter.models import Subscriber
from apps.newsletter.tests.factories import SubscriberFactory


@pytest.mark.django_db
def test_confirming_activates_the_subscription(client):
    subscriber = SubscriberFactory(is_confirmed=False)

    response = client.get(reverse("newsletter:confirm", args=[subscriber.token]))

    assert response.status_code == 200
    subscriber.refresh_from_db()
    assert subscriber.is_confirmed is True
    assert subscriber.confirmed_at is not None


@pytest.mark.django_db
def test_one_click_unsubscribe_needs_no_login(client):
    subscriber = SubscriberFactory()

    response = client.get(reverse("newsletter:unsubscribe", args=[subscriber.token]))

    assert response.status_code == 200
    subscriber.refresh_from_db()
    assert subscriber.is_active is False
    assert subscriber.unsubscribed_at is not None


@pytest.mark.django_db
def test_unsubscribing_takes_effect_exactly_once(client):
    """Mail clients prefetch links, so a second hit must not rewrite the record."""
    subscriber = SubscriberFactory()
    url = reverse("newsletter:unsubscribe", args=[subscriber.token])

    client.get(url)
    subscriber.refresh_from_db()
    first_time = subscriber.unsubscribed_at

    second = client.get(url)

    assert second.status_code == 200
    subscriber.refresh_from_db()
    assert subscriber.unsubscribed_at == first_time


@pytest.mark.django_db
def test_the_rfc_8058_post_works_without_a_csrf_token():
    """The mail provider posting the one-click header has no session and no token."""
    subscriber = SubscriberFactory()
    strict_client = Client(enforce_csrf_checks=True)

    response = strict_client.post(reverse("newsletter:unsubscribe", args=[subscriber.token]))

    assert response.status_code == 200
    subscriber.refresh_from_db()
    assert subscriber.is_active is False


@pytest.mark.django_db
def test_an_unknown_token_is_a_404(client):
    SubscriberFactory()

    # follow=True because a bilingual site's LocaleMiddleware answers a 404 with
    # a redirect to the language-prefixed path first.
    response = client.get(reverse("newsletter:unsubscribe", args=[uuid.uuid4()]), follow=True)

    assert response.status_code == 404


@pytest.mark.django_db
def test_the_token_is_random_not_sequential():
    """A guessable unsubscribe key lets anyone walk the whole list."""
    first = SubscriberFactory()
    second = SubscriberFactory()

    assert first.token != second.token
    assert uuid.UUID(str(first.token)).version == 4
    assert uuid.UUID(str(second.token)).version == 4


@pytest.mark.django_db
def test_an_unsubscribed_address_is_no_longer_mailable():
    subscriber = SubscriberFactory()

    subscriber.is_active = False
    subscriber.save(update_fields=["is_active"])

    assert not Subscriber.objects.mailable().exists()
